from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core._config import settings
from app.core._security import hash_password, verify_password
from app.models._client_profile import ClientProfile
from app.models._communication import Communication
from app.models._decision_log import DecisionLog
from app.models._employee_profile import EmployeeProfile
from app.models._performance_point import PerformancePoint
from app.models._project import Project
from app.models._support_ticket import SupportTicket
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._user import User
from app.models._user_preferences import UserPreferences
from app.services._email_service import EmailService


ALLOWED_THEMES = {"light", "dark"}
ALLOWED_DENSITY = {"all", "summary", "critical"}
ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}


class SettingsService:
    @staticmethod
    def _validate_timezone(timezone_value: str) -> str:
        try:
            ZoneInfo(timezone_value)
        except Exception as exc:
            raise ValueError("Invalid timezone") from exc
        return timezone_value

    @classmethod
    def get_preferences(cls, db: Session, user_id: int) -> UserPreferences:
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if preferences:
            return preferences

        preferences = UserPreferences(user_id=user_id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
        return preferences

    @classmethod
    def update_preferences(cls, db: Session, user_id: int, updates: dict) -> UserPreferences:
        preferences = cls.get_preferences(db, user_id)
        allowed_fields = {
            "timezone",
            "theme",
            "language",
            "ceo_mode",
            "notification_density",
            "default_landing_page",
            "email_notifications",
            "weekly_digest",
        }

        for field, value in updates.items():
            if field not in allowed_fields or value is None:
                continue
            if field == "timezone":
                value = cls._validate_timezone(str(value))
            if field == "theme" and value not in ALLOWED_THEMES:
                raise ValueError("Invalid theme")
            if field == "notification_density" and value not in ALLOWED_DENSITY:
                raise ValueError("Invalid notification density")
            setattr(preferences, field, value)

        db.add(preferences)
        db.commit()
        db.refresh(preferences)
        return preferences

    @classmethod
    def update_profile(cls, db: Session, user: User, updates: dict) -> User:
        full_name = updates.get("full_name")
        timezone_value = updates.get("timezone")

        if full_name is not None:
            user.full_name = full_name.strip()
            db.add(user)

        if timezone_value is not None:
            cls.update_preferences(db, user.id, {"timezone": timezone_value})
        else:
            db.commit()

        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
        if not verify_password(current_password, user.password):
            raise ValueError("Current password is incorrect")

        user.password = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.add(user)
        db.commit()
        return True

    @staticmethod
    def submit_support_ticket(
        db: Session,
        user: User,
        subject: str,
        body: str,
        priority: str = "medium",
    ) -> SupportTicket:
        if user.tenant_id is None:
            raise ValueError("Support tickets require a tenant-scoped user")
        if priority not in ALLOWED_PRIORITIES:
            raise ValueError("Invalid priority")

        ticket = SupportTicket(
            tenant_id=user.tenant_id,
            user_id=user.id,
            subject=subject.strip(),
            body=body.strip(),
            priority=priority,
            status="open",
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        if settings.PLATFORM_OWNER_EMAIL:
            EmailService.send_email(
                to_email=settings.PLATFORM_OWNER_EMAIL,
                subject=f"New support ticket: {ticket.subject}",
                html_body=(
                    f"<p>Tenant ID: {user.tenant_id}</p>"
                    f"<p>User: {escape(user.full_name or user.email)} ({escape(user.email)})</p>"
                    f"<p>Priority: {escape(priority)}</p>"
                    f"<p>Body:</p><p>{escape(ticket.body)}</p>"
                ),
                tenant_id=user.tenant_id,
                template_name="support_ticket_created",
            )

        return ticket

    @classmethod
    def export_user_data(cls, db: Session, user: User) -> dict:
        preferences = cls.get_preferences(db, user.id)
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user.id).first()
        client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()

        assignments = []
        performance_points = []
        decisions = []
        communications = []

        if employee_profile:
            task_assignments = db.query(TaskAssignment).filter(TaskAssignment.employee_id == employee_profile.id).all()
            assignments = [
                {
                    "id": assignment.id,
                    "task_id": assignment.task_id,
                    "status": assignment.status,
                    "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                    "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
                    "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
                    "estimated_hours": assignment.estimated_hours,
                    "actual_hours": assignment.actual_hours,
                    "assignment_confidence": assignment.assignment_confidence,
                }
                for assignment in task_assignments
            ]
            performance_points = [
                {
                    "id": point.id,
                    "project_id": point.project_id,
                    "task_id": point.task_id,
                    "points": point.points,
                    "reason": point.reason,
                    "awarded_at": point.awarded_at.isoformat() if point.awarded_at else None,
                }
                for point in db.query(PerformancePoint).filter(PerformancePoint.employee_id == employee_profile.id).all()
            ]
            decisions.extend(
                db.query(DecisionLog)
                .filter(DecisionLog.entity_type == "employee", DecisionLog.entity_id == employee_profile.id)
                .all()
            )

            assigned_task_ids = [assignment["task_id"] for assignment in assignments]
            if assigned_task_ids:
                employee_tasks = db.query(Task).filter(Task.id.in_(assigned_task_ids)).all()
                employee_project_ids = {task.project_id for task in employee_tasks}
                communications.extend(
                    db.query(Communication)
                    .filter(
                        (Communication.task_id.in_(assigned_task_ids))
                        | (Communication.project_id.in_(employee_project_ids))
                    )
                    .all()
                )

        if client_profile:
            client_projects = db.query(Project).filter(Project.client_id == client_profile.id).all()
            client_project_ids = [project.id for project in client_projects]
            if client_project_ids:
                decisions.extend(
                    db.query(DecisionLog)
                    .filter(DecisionLog.entity_type == "project", DecisionLog.entity_id.in_(client_project_ids))
                    .all()
                )
                communications.extend(
                    db.query(Communication).filter(Communication.project_id.in_(client_project_ids)).all()
                )

        if user.role in {"admin", "ceo"}:
            admin_projects = db.query(Project).filter(Project.admin_id == user.id).all()
            admin_project_ids = [project.id for project in admin_projects]
            if admin_project_ids:
                decisions.extend(
                    db.query(DecisionLog)
                    .filter(DecisionLog.entity_type == "project", DecisionLog.entity_id.in_(admin_project_ids))
                    .all()
                )
                communications.extend(
                    db.query(Communication).filter(Communication.project_id.in_(admin_project_ids)).all()
                )

        decision_payload = []
        seen_decision_ids = set()
        for decision in decisions:
            if decision.id in seen_decision_ids:
                continue
            seen_decision_ids.add(decision.id)
            decision_payload.append(
                {
                    "id": decision.id,
                    "decision_type": decision.decision_type,
                    "entity_type": decision.entity_type,
                    "entity_id": decision.entity_id,
                    "confidence": decision.confidence,
                    "decision_taken": decision.decision_taken,
                    "reasoning": decision.reasoning,
                    "created_at": decision.created_at.isoformat() if decision.created_at else None,
                }
            )

        communication_payload = []
        seen_communication_ids = set()
        for communication in communications:
            if communication.id in seen_communication_ids:
                continue
            seen_communication_ids.add(communication.id)
            communication_payload.append(
                {
                    "id": communication.id,
                    "type": communication.type,
                    "from_actor": communication.from_actor,
                    "to_actor": communication.to_actor,
                    "subject": communication.subject,
                    "body": communication.body,
                    "project_id": communication.project_id,
                    "task_id": communication.task_id,
                    "sent_at": communication.sent_at.isoformat() if communication.sent_at else None,
                    "status": communication.status,
                }
            )

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "created_at": None,
            },
            "preferences": {
                "id": preferences.id,
                "user_id": preferences.user_id,
                "timezone": preferences.timezone,
                "theme": preferences.theme,
                "language": preferences.language,
                "ceo_mode": preferences.ceo_mode,
                "notification_density": preferences.notification_density,
                "default_landing_page": preferences.default_landing_page,
                "email_notifications": preferences.email_notifications,
                "weekly_digest": preferences.weekly_digest,
                "created_at": preferences.created_at.isoformat() if preferences.created_at else None,
                "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None,
            },
            "employee_profile": {
                "id": employee_profile.id,
                "skills": employee_profile.skills,
                "max_capacity": employee_profile.max_capacity,
                "current_load": employee_profile.current_load,
                "department": employee_profile.department,
                "availability_status": employee_profile.availability_status,
            }
            if employee_profile
            else None,
            "task_assignments": assignments,
            "performance_points": performance_points,
            "decisions_involving_user": decision_payload,
            "communications_involving_user": communication_payload,
        }
