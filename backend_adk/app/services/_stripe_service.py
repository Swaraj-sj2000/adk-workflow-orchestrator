from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core._config import settings
from app.models._project import Project
from app.models._tenant import Tenant
from app.models._tenant_settings import TenantSettings
from app.models._user import User
from app.services._email_service import EmailService


class StripeService:
    PRICE_MAP = {
        "starter": "STRIPE_STARTER_PRICE_ID",
        "growth": "STRIPE_GROWTH_PRICE_ID",
        "enterprise": "STRIPE_ENTERPRISE_PRICE_ID",
    }

    @staticmethod
    def _stripe():
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @classmethod
    def _get_or_create_settings(cls, db: Session, tenant_id: int) -> TenantSettings:
        tenant_settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first()
        if tenant_settings:
            return tenant_settings
        tenant_settings = TenantSettings(tenant_id=tenant_id)
        db.add(tenant_settings)
        db.flush()
        return tenant_settings

    @classmethod
    def _tenant_admins(cls, db: Session, tenant_id: int) -> list[User]:
        return (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.role.in_(["admin", "ceo"]))
            .all()
        )

    @staticmethod
    def _tenant_name(db: Session, tenant_id: int) -> str:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return tenant.name if tenant else f"Tenant {tenant_id}"

    @classmethod
    def _price_id_for_plan(cls, plan_tier: str) -> str:
        env_name = cls.PRICE_MAP.get(plan_tier)
        if not env_name:
            raise ValueError("Unsupported plan tier")
        price_id = getattr(settings, env_name, "")
        if not price_id:
            raise ValueError(f"Stripe price ID not configured for plan '{plan_tier}'")
        return price_id

    @staticmethod
    def _project_meta(project: Project) -> dict:
        return dict(project.custom_fields or {})

    @staticmethod
    def _save_project_meta(project: Project, meta: dict) -> None:
        project.custom_fields = meta

    @classmethod
    def create_tenant_subscription(
        cls,
        db: Session,
        tenant_id: int,
        plan_tier: str,
        admin_email: str,
        company_name: str,
    ) -> dict:
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe is not configured")

        stripe = cls._stripe()
        price_id = cls._price_id_for_plan(plan_tier)
        tenant_settings = cls._get_or_create_settings(db, tenant_id)

        customer_id = tenant_settings.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=admin_email,
                name=company_name,
                metadata={"tenant_id": str(tenant_id)},
            )
            customer_id = customer.id

        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.FRONTEND_URL.rstrip('/')}/settings?billing=success",
            cancel_url=f"{settings.FRONTEND_URL.rstrip('/')}/settings?billing=cancelled",
            metadata={"tenant_id": str(tenant_id), "plan_tier": plan_tier},
        )

        tenant_settings.stripe_customer_id = customer_id
        tenant_settings.plan_tier = plan_tier
        tenant_settings.stripe_plan_id = price_id
        db.add(tenant_settings)
        db.commit()
        db.refresh(tenant_settings)

        return {
            "checkout_url": checkout_session.url,
            "client_secret": getattr(checkout_session, "client_secret", None),
            "customer_id": customer_id,
            "plan_tier": plan_tier,
        }

    @classmethod
    def get_billing_portal_url(cls, db: Session, tenant_id: int) -> str:
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe is not configured")

        tenant_settings = cls._get_or_create_settings(db, tenant_id)
        if not tenant_settings.stripe_customer_id:
            raise ValueError("No Stripe customer exists for this tenant")

        stripe = cls._stripe()
        session = stripe.billing_portal.Session.create(
            customer=tenant_settings.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL.rstrip('/')}/settings",
        )
        return session.url

    @classmethod
    def handle_stripe_webhook(cls, payload: bytes, sig_header: str, db: Session) -> None:
        if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe webhook configuration is incomplete")

        stripe = cls._stripe()
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        event_type = event["type"]
        data = event["data"]["object"]
        customer_id = data.get("customer")
        if not customer_id:
            return

        tenant_settings = db.query(TenantSettings).filter(TenantSettings.stripe_customer_id == customer_id).first()
        if not tenant_settings:
            return

        if event_type == "invoice.paid":
            tenant_settings.suspended = False
            tenant_settings.suspension_reason = None
            tenant_settings.grace_period_ends_at = None
            tenant_settings.stripe_subscription_id = data.get("subscription") or tenant_settings.stripe_subscription_id
            period_end = data.get("period_end")
            tenant_settings.next_billing_date = (
                datetime.utcfromtimestamp(period_end) if period_end else tenant_settings.next_billing_date
            )
            db.add(tenant_settings)
            db.commit()
            return

        if event_type == "invoice.payment_failed":
            tenant_settings.grace_period_ends_at = cls._now() + timedelta(days=settings.GRACE_PERIOD_DAYS)
            tenant_settings.stripe_subscription_id = data.get("subscription") or tenant_settings.stripe_subscription_id
            db.add(tenant_settings)
            db.commit()
            grace_ends = tenant_settings.grace_period_ends_at.isoformat() if tenant_settings.grace_period_ends_at else "soon"
            tenant_name = cls._tenant_name(db, tenant_settings.tenant_id)
            for admin in cls._tenant_admins(db, tenant_settings.tenant_id):
                EmailService.send_suspension_warning_email(
                    to_email=admin.email,
                    company_name=tenant_name,
                    grace_period_ends=grace_ends,
                )
            return

        if event_type == "customer.subscription.deleted":
            tenant_settings.suspended = True
            tenant_settings.suspension_reason = "subscription_cancelled"
            tenant_settings.stripe_subscription_id = data.get("id") or tenant_settings.stripe_subscription_id
            db.add(tenant_settings)
            db.commit()
            tenant_name = cls._tenant_name(db, tenant_settings.tenant_id)
            for admin in cls._tenant_admins(db, tenant_settings.tenant_id):
                EmailService.send_suspension_email(
                    to_email=admin.email,
                    company_name=tenant_name,
                )

    @classmethod
    def check_and_enforce_grace_periods(cls, db: Session) -> None:
        now = cls._now()
        due_tenants = (
            db.query(TenantSettings)
            .filter(
                TenantSettings.grace_period_ends_at.isnot(None),
                TenantSettings.grace_period_ends_at < now,
                TenantSettings.suspended.is_(False),
            )
            .all()
        )
        for tenant_settings in due_tenants:
            tenant_settings.suspended = True
            tenant_settings.suspension_reason = "payment_failed"
            db.add(tenant_settings)
            tenant_name = cls._tenant_name(db, tenant_settings.tenant_id)
            for admin in cls._tenant_admins(db, tenant_settings.tenant_id):
                EmailService.send_suspension_email(
                    to_email=admin.email,
                    company_name=tenant_name,
                )
        db.commit()

    @classmethod
    def create_project_invoice(
        cls,
        db: Session,
        project_id: int,
        amount: float,
        due_date: datetime,
        admin: User,
    ) -> dict:
        project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == admin.tenant_id).first()
        if not project:
            raise ValueError("Project not found")

        meta = cls._project_meta(project)
        invoices = list(meta.get("invoices") or [])
        invoice_record = {
            "invoice_id": f"invoice-{project.id}-{len(invoices) + 1}",
            "amount": round(float(amount), 2),
            "due_date": due_date.isoformat(),
            "created_at": cls._now().isoformat(),
            "created_by": admin.id,
            "collection_mode": "manual",
            "status": "issued",
        }

        tenant_settings = cls._get_or_create_settings(db, admin.tenant_id)
        if settings.STRIPE_SECRET_KEY and tenant_settings.stripe_customer_id and project.client and project.client.user:
            try:
                stripe = cls._stripe()
                stripe_invoice = stripe.Invoice.create(
                    customer=tenant_settings.stripe_customer_id,
                    collection_method="send_invoice",
                    days_until_due=max((due_date.date() - cls._now().date()).days, 1),
                    metadata={"project_id": str(project.id), "tenant_id": str(admin.tenant_id)},
                    description=f"Project invoice for {project.name}",
                )
                invoice_record["collection_mode"] = "stripe"
                invoice_record["stripe_invoice_id"] = stripe_invoice.id
            except Exception:
                invoice_record["collection_mode"] = "manual"

        invoices.append(invoice_record)
        meta["invoices"] = invoices
        cls._save_project_meta(project, meta)
        db.add(project)
        db.commit()
        return invoice_record

    @classmethod
    def apply_payment_hold(cls, db: Session, project_id: int, admin: User) -> Project:
        project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == admin.tenant_id).first()
        if not project:
            raise ValueError("Project not found")

        meta = cls._project_meta(project)
        meta["payment_hold_active"] = True
        meta["payment_hold_applied_at"] = cls._now().isoformat()
        meta["payment_hold_applied_by"] = admin.id
        meta["payment_hold_previous_status"] = project.payment_status
        project.payment_status = "disputed"
        cls._save_project_meta(project, meta)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @classmethod
    def lift_payment_hold(cls, db: Session, project_id: int, admin: User) -> Project:
        project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == admin.tenant_id).first()
        if not project:
            raise ValueError("Project not found")

        meta = cls._project_meta(project)
        previous_status = meta.get("payment_hold_previous_status")
        meta["payment_hold_active"] = False
        meta["payment_hold_lifted_at"] = cls._now().isoformat()
        meta["payment_hold_lifted_by"] = admin.id
        if previous_status:
            project.payment_status = previous_status
        cls._save_project_meta(project, meta)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
