# app/services/_event_service.py
from sqlalchemy.orm import Session
from app.db._database import SessionLocal
from app.models._event_queue import EventQueue
from app.models._task import Task
from app.models._project import Project
from app.services._assignment_engine import AssignmentEngine
from app.core._logging import get_logger
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json
import time

logger = get_logger(__name__)


def process_event_queue_batch_async(batch_size: int = 10) -> Dict[str, Any]:
    """
    Background-safe queue processor.
    Opens a fresh DB session so it can be used from FastAPI background tasks.
    """
    db = SessionLocal()
    try:
        service = EventService(db)
        return service.process_pending_events(batch_size=batch_size)
    finally:
        db.close()


def run_event_worker_loop(batch_size: int = 10, poll_interval_seconds: float = 2.0, max_cycles: Optional[int] = None) -> None:
    """
    Poll the event queue in a long-running loop.
    Intended for a standalone worker process outside the API server.
    """
    logger.info(f"Event worker started: batch_size={batch_size}, poll_interval={poll_interval_seconds}s")
    cycles = 0
    while True:
        result = process_event_queue_batch_async(batch_size=batch_size)
        cycles += 1

        processed_any = (result.get("processed", 0) + result.get("failed", 0)) > 0
        if processed_any:
            logger.info(
                f"Event worker cycle {cycles}: processed={result['processed']}, "
                f"failed={result['failed']}, total={result['total']}"
            )

        if max_cycles is not None and cycles >= max_cycles:
            logger.info(f"Event worker stopping after {cycles} cycles")
            break

        time.sleep(0 if processed_any else poll_interval_seconds)


class EventService:
    """
    Manages event queue for async system operations.
    Supports task routing, assignment triggering, and system-wide events.
    """
    
    MAX_RETRIES = 3
    
    def __init__(self, db: Session):
        self.db = db
        self.handlers = self._init_handlers()
    
    def publish_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: Dict[str, Any]
    ) -> EventQueue:
        """Publish an event to the queue."""
        logger.info(f"Publishing event: type={event_type}, entity={entity_type}:{entity_id}")
        event = EventQueue(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            status="pending"
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        logger.debug(f"Event published: event_id={event.id}")
        return event
    
    def process_pending_events(self, batch_size: int = 10) -> Dict:
        """Process pending events from the queue."""
        pending_events = self.db.query(EventQueue).filter(
            EventQueue.status == "pending"
        ).limit(batch_size).all()
        
        logger.debug(f"Processing {len(pending_events)} pending events")
        
        results = {
            "total": len(pending_events),
            "processed": 0,
            "failed": 0,
            "details": []
        }
        
        for event in pending_events:
            try:
                logger.debug(f"Processing event {event.id}: {event.event_type}_{event.entity_type}")
                self._process_event(event)
                event.status = "completed"
                event.processed_at = datetime.utcnow()
                results["processed"] += 1
                logger.info(f"Event {event.id} processed successfully")
            except Exception as e:
                event.retry_count += 1
                event.error_message = str(e)
                
                if event.retry_count >= self.MAX_RETRIES:
                    event.status = "failed"
                    results["failed"] += 1
                    logger.error(f"Event {event.id} failed after {event.retry_count} retries: {e}", exc_info=True)
                else:
                    logger.warning(f"Event {event.id} retry {event.retry_count}/{self.MAX_RETRIES}: {e}")
                
            self.db.merge(event)
            results["details"].append({
                "event_id": event.id,
                "event_type": event.event_type,
                "status": event.status,
                "retries": event.retry_count
            })
        
        self.db.commit()
        return results
    
    def _process_event(self, event: EventQueue) -> None:
        """Route event to appropriate handler."""
        handler_key = f"{event.event_type}_{event.entity_type}".lower()
        
        if handler_key in self.handlers:
            handler = self.handlers[handler_key]
            handler(event)
        else:
            # Log unknown event type but don't fail
            logger.warning(f"Unknown event type: {handler_key} for event_id={event.id}")
    
    def _init_handlers(self) -> Dict[str, Callable]:
        """Initialize event handlers."""
        return {
            "task_created_task": self._handle_task_created,
            "task_updated_task": self._handle_task_updated,
            "project_created_project": self._handle_project_created,
            "assignment_complete_task": self._handle_assignment_complete,
            "project_execution_signal_project": self._handle_project_execution_signal,
            "send_email_email": self._handle_send_email,
        }

    def _handle_send_email(self, event: EventQueue) -> None:
        """Handle queued email sends (processed by worker)."""
        from app.core._config import settings
        from app.services._email_service import EmailService

        payload = event.payload or {}
        to_email = payload.get("to_email")
        subject = payload.get("subject")
        html_body = payload.get("html_body")
        tenant_id = payload.get("tenant_id")
        template_name = payload.get("template_name", "generic")

        # If SendGrid not configured, persist a failed delivery log
        if not settings.SENDGRID_API_KEY:
            EmailService._persist_delivery_log(
                tenant_id=tenant_id,
                to_email=to_email or "",
                subject=subject or "",
                template_name=template_name,
                status="failed",
                error_message="SENDGRID_API_KEY not configured",
            )
            return

        # Attempt to send via SendGrid
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Email, Mail

            client = SendGridAPIClient(settings.SENDGRID_API_KEY)
            message = Mail(
                from_email=Email(settings.EMAIL_FROM, settings.EMAIL_FROM_NAME),
                to_emails=(to_email or ""),
                subject=(subject or ""),
                html_content=(html_body or ""),
            )
            response = client.send(message)
            status = "sent" if response.status_code in (200, 202) else "failed"
            message_id = EmailService._message_headers_value(response.headers, "X-Message-Id")
            EmailService._persist_delivery_log(
                tenant_id=tenant_id,
                to_email=to_email or "",
                subject=subject or "",
                template_name=template_name,
                sendgrid_message_id=message_id,
                status=status,
                sent_at=None if status != "sent" else None,
                error_message=None if status == "sent" else f"Unexpected SendGrid status: {response.status_code}",
            )
        except Exception as exc:
            EmailService._persist_delivery_log(
                tenant_id=tenant_id,
                to_email=to_email or "",
                subject=subject or "",
                template_name=template_name,
                status="failed",
                error_message=str(exc),
            )
            raise
    
    def _handle_task_created(self, event: EventQueue) -> None:
        """Handle new task creation - trigger assignment."""
        task = self.db.query(Task).filter(Task.id == event.entity_id).first()
        
        if task and task.status == "pending":
            engine = AssignmentEngine(self.db)
            assignment, confidence, reasoning = engine.assign_task(task)
    
    def _handle_task_updated(self, event: EventQueue) -> None:
        """Handle task updates."""
        payload = event.payload
        task = self.db.query(Task).filter(Task.id == event.entity_id).first()
        
        if task:
            if "status" in payload:
                task.status = payload["status"]
            if "progress" in payload:
                # Update progress tracking
                pass
            self.db.merge(task)
            self.db.commit()
    
    def _handle_project_created(self, event: EventQueue) -> None:
        """Handle new project creation."""
        project = self.db.query(Project).filter(Project.id == event.entity_id).first()
        
        if project:
            # Initialize project metrics/structure
            project.status = "planning"
            self.db.merge(project)
            self.db.commit()
    
    def _handle_assignment_complete(self, event: EventQueue) -> None:
        """Handle task assignment completion."""
        payload = event.payload
        task = self.db.query(Task).filter(Task.id == event.entity_id).first()
        
        if task:
            task.status = "running"
            self.db.merge(task)
            self.db.commit()

    def _handle_project_execution_signal(self, event: EventQueue) -> None:
        """Run the multi-agent project loop when execution state changes."""
        from app.services._multi_agent_orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator(self.db)
        orchestrator.run_project_execution_loop(
            project_id=event.entity_id,
            requested_by=event.payload.get("triggered_by", 0),
            persist_followup_messages=event.payload.get("persist_followup_messages", True),
        )
    
    def get_pending_event_count(self) -> int:
        """Get count of pending events."""
        return self.db.query(EventQueue).filter(
            EventQueue.status == "pending"
        ).count()
    
    def get_failed_events(self, limit: int = 20) -> list:
        """Get failed events for review."""
        return self.db.query(EventQueue).filter(
            EventQueue.status == "failed"
        ).order_by(EventQueue.created_at.desc()).limit(limit).all()

    def get_queue_status(self) -> Dict[str, Any]:
        pending = self.db.query(EventQueue).filter(EventQueue.status == "pending").count()
        processing = self.db.query(EventQueue).filter(EventQueue.status == "processing").count()
        completed = self.db.query(EventQueue).filter(EventQueue.status == "completed").count()
        failed = self.db.query(EventQueue).filter(EventQueue.status == "failed").count()

        latest = self.db.query(EventQueue).order_by(EventQueue.created_at.desc()).first()
        return {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "latest_event": {
                "id": latest.id,
                "event_type": latest.event_type,
                "entity_type": latest.entity_type,
                "entity_id": latest.entity_id,
                "status": latest.status,
                "created_at": latest.created_at.isoformat() if latest.created_at else None,
            } if latest else None,
        }
