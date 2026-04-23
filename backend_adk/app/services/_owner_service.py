from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Optional

from sqlalchemy.orm import Session

from app.models._platform_audit_log import PlatformAuditLog
from app.models._project import Project
from app.models._support_ticket import SupportTicket
from app.models._tenant import Tenant
from app.models._tenant_settings import TenantSettings
from app.models._user import User
from app.services._email_service import EmailService


PLAN_MRR_ESTIMATES = {
    "trial": 0.0,
    "starter": 99.0,
    "growth": 299.0,
    "enterprise": 999.0,
}


class OwnerService:
    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @classmethod
    def _get_or_create_settings(cls, db: Session, tenant_id: int) -> TenantSettings:
        settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first()
        if settings:
            return settings

        settings = TenantSettings(tenant_id=tenant_id)
        db.add(settings)
        db.flush()
        return settings

    @staticmethod
    def _log_action(db: Session, action: str, tenant_id: Optional[int], details: Optional[dict] = None) -> None:
        db.add(
            PlatformAuditLog(
                action=action,
                tenant_id=tenant_id,
                details=details,
            )
        )

    @staticmethod
    def _tenant_admins(db: Session, tenant_id: int) -> list[User]:
        return (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.role.in_(["admin", "ceo"]))
            .all()
        )

    @classmethod
    def list_tenants(cls, db: Session) -> list:
        tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
        settings_by_tenant = {
            settings.tenant_id: settings
            for settings in db.query(TenantSettings).all()
        }
        users = db.query(User).all()
        projects = db.query(Project).all()

        users_by_tenant: dict[int, list[User]] = {}
        for user in users:
            if user.tenant_id is None:
                continue
            users_by_tenant.setdefault(user.tenant_id, []).append(user)

        projects_by_tenant: dict[int, list[Project]] = {}
        for project in projects:
            if project.tenant_id is None:
                continue
            projects_by_tenant.setdefault(project.tenant_id, []).append(project)

        payload = []
        for tenant in tenants:
            tenant_settings = settings_by_tenant.get(tenant.id)
            tenant_users = users_by_tenant.get(tenant.id, [])
            tenant_projects = projects_by_tenant.get(tenant.id, [])
            last_project_activity = max(
                (project.created_at for project in tenant_projects if project.created_at),
                default=None,
            )

            payload.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "tenant_slug": tenant.slug,
                    "plan_tier": tenant_settings.plan_tier if tenant_settings else "trial",
                    "suspended": tenant_settings.suspended if tenant_settings else False,
                    "suspension_reason": tenant_settings.suspension_reason if tenant_settings else None,
                    "user_count": len(tenant_users),
                    "admin_count": sum(1 for user in tenant_users if user.role == "admin"),
                    "employee_count": sum(1 for user in tenant_users if user.role == "employee"),
                    "client_count": sum(1 for user in tenant_users if user.role == "client"),
                    "project_count": len(tenant_projects),
                    "active_project_count": sum(
                        1 for project in tenant_projects if project.status not in {"completed", "cancelled"}
                    ),
                    "stripe_customer_id": tenant_settings.stripe_customer_id if tenant_settings else None,
                    "next_billing_date": tenant_settings.next_billing_date.isoformat()
                    if tenant_settings and tenant_settings.next_billing_date
                    else None,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    "last_active_at": (last_project_activity or tenant.created_at).isoformat()
                    if (last_project_activity or tenant.created_at)
                    else None,
                    "admin_emails": [
                        admin.email for admin in tenant_users if admin.role in {"admin", "ceo"}
                    ],
                }
            )
        return payload

    @classmethod
    def suspend_tenant(cls, db: Session, tenant_id: int, reason: str) -> TenantSettings:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        settings = cls._get_or_create_settings(db, tenant_id)
        settings.suspended = True
        settings.suspension_reason = reason
        settings.suspended_at = cls._now()
        db.add(settings)
        cls._log_action(db, "tenant_suspended", tenant_id, {"reason": reason})
        db.commit()
        db.refresh(settings)

        for admin in cls._tenant_admins(db, tenant_id):
            EmailService.send_suspension_email(
                to_email=admin.email,
                company_name=tenant.name if tenant else (admin.full_name or admin.email),
            )
        return settings

    @classmethod
    def activate_tenant(cls, db: Session, tenant_id: int) -> TenantSettings:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        settings = cls._get_or_create_settings(db, tenant_id)
        settings.suspended = False
        settings.suspension_reason = None
        settings.suspended_at = None
        db.add(settings)
        cls._log_action(db, "tenant_activated", tenant_id, None)
        db.commit()
        db.refresh(settings)

        for admin in cls._tenant_admins(db, tenant_id):
            EmailService.send_email(
                to_email=admin.email,
                subject="Your account has been reactivated",
                html_body=(
                    f"<p>{escape(tenant.name if tenant else (admin.full_name or admin.email))}, your account has been reactivated.</p>"
                    "<p>You can sign back in and continue using AI Workforce Orchestrator.</p>"
                ),
                tenant_id=tenant_id,
                template_name="account_reactivated",
            )
        return settings

    @classmethod
    def get_platform_metrics(cls, db: Session) -> dict:
        tenants = db.query(Tenant).all()
        settings = db.query(TenantSettings).all()
        users = db.query(User).all()
        projects = db.query(Project).all()

        settings_by_tenant = {item.tenant_id: item for item in settings}
        total_tenants = len(tenants)
        suspended_tenants = sum(1 for tenant in tenants if settings_by_tenant.get(tenant.id) and settings_by_tenant[tenant.id].suspended)
        trial_tenants = sum(1 for tenant in tenants if (settings_by_tenant.get(tenant.id).plan_tier if settings_by_tenant.get(tenant.id) else "trial") == "trial")
        paid_tenants = sum(1 for tenant in tenants if (settings_by_tenant.get(tenant.id).plan_tier if settings_by_tenant.get(tenant.id) else "trial") != "trial")
        mrr_estimate = sum(
            PLAN_MRR_ESTIMATES.get(
                settings_by_tenant.get(tenant.id).plan_tier if settings_by_tenant.get(tenant.id) else "trial",
                0.0,
            )
            for tenant in tenants
        )

        current_month = cls._now().month
        current_year = cls._now().year
        new_tenants_this_month = sum(
            1
            for tenant in tenants
            if tenant.created_at and tenant.created_at.month == current_month and tenant.created_at.year == current_year
        )

        return {
            "total_tenants": total_tenants,
            "active_tenants": total_tenants - suspended_tenants,
            "suspended_tenants": suspended_tenants,
            "trial_tenants": trial_tenants,
            "paid_tenants": paid_tenants,
            "total_users_across_platform": len(users),
            "total_projects_across_platform": len(projects),
            "mrr_estimate": round(mrr_estimate, 2),
            "new_tenants_this_month": new_tenants_this_month,
        }

    @classmethod
    def list_support_tickets(cls, db: Session, status: str | None = None) -> list:
        query = (
            db.query(SupportTicket, Tenant, User)
            .join(Tenant, Tenant.id == SupportTicket.tenant_id)
            .join(User, User.id == SupportTicket.user_id)
        )
        if status:
            query = query.filter(SupportTicket.status == status)

        rows = query.order_by(SupportTicket.created_at.desc()).all()
        payload = []
        for ticket, tenant, user in rows:
            payload.append(
                {
                    "id": ticket.id,
                    "tenant_id": ticket.tenant_id,
                    "tenant_name": tenant.name,
                    "user_id": ticket.user_id,
                    "user_email": user.email,
                    "user_full_name": user.full_name,
                    "subject": ticket.subject,
                    "body": ticket.body,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "admin_response": ticket.admin_response,
                    "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                    "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                    "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                }
            )
        return payload

    @classmethod
    def respond_to_ticket(cls, db: Session, ticket_id: int, response: str) -> SupportTicket:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            raise ValueError("Support ticket not found")

        user = db.query(User).filter(User.id == ticket.user_id).first()
        ticket.admin_response = response
        ticket.status = "resolved"
        ticket.resolved_at = cls._now()
        db.add(ticket)
        cls._log_action(db, "ticket_resolved", ticket.tenant_id, {"ticket_id": ticket.id})
        db.commit()
        db.refresh(ticket)

        if user:
            EmailService.send_email(
                to_email=user.email,
                subject=f"Support response: {ticket.subject}",
                html_body=(
                    f"<p>Hello {escape(user.full_name or user.email)},</p>"
                    f"<p>Your support ticket has been resolved.</p>"
                    f"<p><strong>Response:</strong></p><p>{escape(response)}</p>"
                ),
                tenant_id=ticket.tenant_id,
                template_name="support_response",
            )
        return ticket
