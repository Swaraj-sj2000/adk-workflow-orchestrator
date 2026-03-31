# app/services/_event_service.py
from sqlalchemy.orm import Session
from app.models._event_queue import EventQueue
from app.models._task import Task
from app.models._project import Project
from app.services._assignment_engine import AssignmentEngine
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json


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
        return event
    
    def process_pending_events(self, batch_size: int = 10) -> Dict:
        """Process pending events from the queue."""
        pending_events = self.db.query(EventQueue).filter(
            EventQueue.status == "pending"
        ).limit(batch_size).all()
        
        results = {
            "total": len(pending_events),
            "processed": 0,
            "failed": 0,
            "details": []
        }
        
        for event in pending_events:
            try:
                self._process_event(event)
                event.status = "completed"
                event.processed_at = datetime.utcnow()
                results["processed"] += 1
            except Exception as e:
                event.retry_count += 1
                event.error_message = str(e)
                
                if event.retry_count >= self.MAX_RETRIES:
                    event.status = "failed"
                    results["failed"] += 1
                
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
            print(f"Unknown event type: {handler_key}")
    
    def _init_handlers(self) -> Dict[str, Callable]:
        """Initialize event handlers."""
        return {
            "task_created_task": self._handle_task_created,
            "task_updated_task": self._handle_task_updated,
            "project_created_project": self._handle_project_created,
            "assignment_complete_task": self._handle_assignment_complete
        }
    
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
