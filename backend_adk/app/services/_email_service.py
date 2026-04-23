from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Optional

from app.core._config import settings
from app.core._logging import get_logger
from app.db._database import SessionLocal
from app.models._email_delivery_log import EmailDeliveryLog


logger = get_logger(__name__)


class EmailService:
    @staticmethod
    def _persist_delivery_log(
        *,
        to_email: str,
        subject: str,
        template_name: str,
        tenant_id: Optional[int] = None,
        sendgrid_message_id: Optional[str] = None,
        status: str = "queued",
        error_message: Optional[str] = None,
        sent_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
    ) -> None:
        db = SessionLocal()
        try:
            db.add(
                EmailDeliveryLog(
                    tenant_id=tenant_id,
                    to_email=to_email,
                    subject=subject,
                    template_name=template_name,
                    sendgrid_message_id=sendgrid_message_id,
                    status=status,
                    error_message=error_message,
                    sent_at=sent_at,
                    delivered_at=delivered_at,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.error("Failed to persist email delivery log", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _sendgrid_client():
        from sendgrid import SendGridAPIClient

        return SendGridAPIClient(settings.SENDGRID_API_KEY)

    @staticmethod
    def _message_headers_value(headers: Any, key: str) -> Optional[str]:
        if not headers:
            return None
        return headers.get(key) or headers.get(key.lower()) or headers.get(key.upper())

    @staticmethod
    def _app_link(path: str = "") -> str:
        base = settings.FRONTEND_URL.rstrip("/")
        if not path:
            return base
        return f"{base}/{path.lstrip('/')}"

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        tenant_id: int | None = None,
        template_name: str = "generic",
    ) -> bool:
        normalized_email = (to_email or "").strip().lower()
        if not normalized_email:
            logger.warning("Skipping email send because recipient email is empty")
            return False

        if not settings.SENDGRID_API_KEY:
            cls._persist_delivery_log(
                tenant_id=tenant_id,
                to_email=normalized_email,
                subject=subject,
                template_name=template_name,
                status="failed",
                error_message="SENDGRID_API_KEY not configured",
            )
            logger.warning("SENDGRID_API_KEY not configured; email delivery skipped")
            return False

        try:
            from sendgrid.helpers.mail import Email, Mail

            message = Mail(
                from_email=Email(settings.EMAIL_FROM, settings.EMAIL_FROM_NAME),
                to_emails=normalized_email,
                subject=subject,
                html_content=html_body,
            )
            response = cls._sendgrid_client().send(message)
            status = "sent" if response.status_code in (200, 202) else "failed"
            message_id = cls._message_headers_value(response.headers, "X-Message-Id")
            cls._persist_delivery_log(
                tenant_id=tenant_id,
                to_email=normalized_email,
                subject=subject,
                template_name=template_name,
                sendgrid_message_id=message_id,
                status=status,
                sent_at=datetime.utcnow() if status == "sent" else None,
                error_message=None if status == "sent" else f"Unexpected SendGrid status: {response.status_code}",
            )
            if status != "sent":
                logger.warning(
                    "SendGrid returned non-success status for email delivery: status_code=%s subject=%s to=%s",
                    response.status_code,
                    subject,
                    normalized_email,
                )
            return status == "sent"
        except Exception as exc:
            logger.error("Email delivery failed", exc_info=True)
            cls._persist_delivery_log(
                tenant_id=tenant_id,
                to_email=normalized_email,
                subject=subject,
                template_name=template_name,
                status="failed",
                error_message=str(exc),
            )
            return False

    @classmethod
    def send_invite_email(
        cls,
        to_email: str,
        inviter_name: str,
        project_name: str,
        role_title: str,
        invite_token: str,
        tenant_id: int,
    ) -> bool:
        safe_role = escape(role_title or "Contributor")
        subject = f"You've been invited to join {project_name} as {role_title}"
        html_body = (
            f"<p>{escape(inviter_name)} invited you to join <strong>{escape(project_name)}</strong>.</p>"
            f"<p>Role: <strong>{safe_role}</strong></p>"
            f"<p><a href=\"{cls._app_link(f'accept-invite?token={invite_token}')}\">Accept invite</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            tenant_id=tenant_id,
            template_name="invite",
        )

    @classmethod
    def send_welcome_email(cls, to_email: str, full_name: str, role: str) -> bool:
        html_body = (
            f"<p>Welcome {escape(full_name or to_email)}.</p>"
            f"<p>Your {escape(role)} account has been created in AI Workforce Orchestrator.</p>"
            f"<p><a href=\"{cls._app_link()}\">Log in to your workspace</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject="Welcome to AI Workforce Orchestrator",
            html_body=html_body,
            template_name="welcome",
        )

    @classmethod
    def send_password_reset_email(cls, to_email: str, reset_token: str) -> bool:
        html_body = (
            "<p>We received a request to reset your password.</p>"
            f"<p><a href=\"{cls._app_link(f'reset-password?token={reset_token}')}\">Reset password</a></p>"
            "<p>This link is valid for 1 hour.</p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject="Reset your password",
            html_body=html_body,
            template_name="password_reset",
        )

    @classmethod
    def send_task_assignment_email(
        cls,
        to_email: str,
        employee_name: str,
        task_description: str,
        project_name: str,
        deadline: str,
        estimated_hours: float,
    ) -> bool:
        subject = f"New task assigned: {(task_description or '')[:50]}"
        html_body = (
            f"<p>Hi {escape(employee_name or to_email)},</p>"
            f"<p>You have been assigned a new task in <strong>{escape(project_name)}</strong>.</p>"
            f"<p>Task: {escape(task_description)}</p>"
            f"<p>Deadline: {escape(deadline)}</p>"
            f"<p>Estimated hours: {estimated_hours}</p>"
            f"<p><a href=\"{cls._app_link()}\">Open workspace</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            template_name="task_assignment",
        )

    @classmethod
    def send_blocker_alert_email(
        cls,
        to_email: str,
        recipient_name: str,
        task_description: str,
        blocker_description: str,
        severity: str,
        project_name: str,
    ) -> bool:
        subject = f"[{(severity or 'medium').upper()}] Blocker raised on {project_name}"
        html_body = (
            f"<p>Hi {escape(recipient_name or to_email)},</p>"
            f"<p>A blocker has been raised in <strong>{escape(project_name)}</strong>.</p>"
            f"<p>Task: {escape(task_description)}</p>"
            f"<p>Blocker: {escape(blocker_description)}</p>"
            f"<p>Severity: {escape(severity)}</p>"
            f"<p><a href=\"{cls._app_link()}\">Review in app</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            template_name="blocker_alert",
        )

    @classmethod
    def send_escalation_alert_email(
        cls,
        to_email: str,
        recipient_name: str,
        project_name: str,
        reason: str,
        workflow_run_id: int,
    ) -> bool:
        html_body = (
            f"<p>Hi {escape(recipient_name or to_email)},</p>"
            f"<p>Human review is required for <strong>{escape(project_name)}</strong>.</p>"
            f"<p>Reason: {escape(reason)}</p>"
            f"<p>Workflow run: {workflow_run_id}</p>"
            f"<p><a href=\"{cls._app_link()}\">Open app</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject=f"Human review required: {project_name}",
            html_body=html_body,
            template_name="escalation_alert",
        )

    @classmethod
    def send_weekly_digest_email(cls, to_email: str, recipient_name: str, digest_data: dict) -> bool:
        top_risks = digest_data.get("top_risks") or []
        risk_items = "".join(f"<li>{escape(str(item))}</li>" for item in top_risks) or "<li>No major risks reported</li>"
        html_body = (
            f"<p>Hi {escape(recipient_name or to_email)},</p>"
            "<p>Here is your weekly project digest:</p>"
            f"<ul>"
            f"<li>Projects on track: {digest_data.get('projects_on_track', 0)}</li>"
            f"<li>Projects at risk: {digest_data.get('projects_at_risk', 0)}</li>"
            f"<li>Projects delayed: {digest_data.get('projects_delayed', 0)}</li>"
            f"<li>Total tasks completed: {digest_data.get('total_tasks_completed', 0)}</li>"
            f"<li>Blockers open: {digest_data.get('blockers_open', 0)}</li>"
            f"</ul>"
            f"<p>Top risks:</p><ul>{risk_items}</ul>"
        )
        return cls.send_email(
            to_email=to_email,
            subject="Weekly Project Digest",
            html_body=html_body,
            template_name="weekly_digest",
        )

    @classmethod
    def send_payment_overdue_email(
        cls,
        to_email: str,
        company_name: str,
        days_overdue: int,
        amount_due: float,
        portal_link: str,
    ) -> bool:
        html_body = (
            f"<p>{escape(company_name)} has an overdue payment.</p>"
            f"<p>Days overdue: {days_overdue}</p>"
            f"<p>Amount due: {amount_due}</p>"
            f"<p><a href=\"{escape(portal_link)}\">Open payment portal</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject=f"Action required: Payment overdue for {company_name}",
            html_body=html_body,
            template_name="payment_overdue",
        )

    @classmethod
    def send_suspension_warning_email(cls, to_email: str, company_name: str, grace_period_ends: str) -> bool:
        html_body = (
            f"<p>{escape(company_name)}, your account is at risk of suspension.</p>"
            f"<p>Grace period ends on {escape(grace_period_ends)}.</p>"
            f"<p><a href=\"{cls._app_link()}\">Open app</a></p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject=f"Your account will be suspended on {grace_period_ends}",
            html_body=html_body,
            template_name="suspension_warning",
        )

    @classmethod
    def send_suspension_email(cls, to_email: str, company_name: str) -> bool:
        html_body = (
            f"<p>{escape(company_name)}, your account has been suspended.</p>"
            "<p>Please contact support for assistance.</p>"
        )
        return cls.send_email(
            to_email=to_email,
            subject="Your account has been suspended",
            html_body=html_body,
            template_name="suspension",
        )
