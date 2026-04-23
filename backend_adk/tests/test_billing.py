"""Billing service tests — Stripe webhook handling + grace period enforcement."""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models._tenant import Tenant
from app.models._tenant_settings import TenantSettings
from app.services._stripe_service import StripeService


@pytest.fixture()
def tenant(db: Session) -> Tenant:
    t = Tenant(name="BillingCo", slug="billingco")
    db.add(t)
    db.flush()
    return t


@pytest.fixture()
def tenant_settings(db: Session, tenant: Tenant) -> TenantSettings:
    ts = TenantSettings(
        tenant_id=tenant.id,
        stripe_customer_id="cus_test123",
        plan_tier="starter",
        suspended=False,
    )
    db.add(ts)
    db.flush()
    return ts


class TestGracePeriodEnforcement:
    def test_tenant_not_suspended_before_grace_end(self, db: Session, tenant_settings: TenantSettings):
        tenant_settings.grace_period_ends_at = datetime.utcnow() + timedelta(days=3)
        db.commit()

        StripeService.check_and_enforce_grace_periods(db)
        db.refresh(tenant_settings)
        assert tenant_settings.suspended is False

    def test_tenant_suspended_after_grace_end(self, db: Session, tenant_settings: TenantSettings):
        tenant_settings.grace_period_ends_at = datetime.utcnow() - timedelta(hours=1)
        tenant_settings.suspended = False
        db.commit()

        with patch.object(StripeService, "_tenant_admins", return_value=[]):
            StripeService.check_and_enforce_grace_periods(db)

        db.refresh(tenant_settings)
        assert tenant_settings.suspended is True
        assert tenant_settings.suspension_reason == "payment_failed"

    def test_already_suspended_not_affected(self, db: Session, tenant_settings: TenantSettings):
        tenant_settings.grace_period_ends_at = datetime.utcnow() - timedelta(hours=1)
        tenant_settings.suspended = True
        db.commit()

        StripeService.check_and_enforce_grace_periods(db)
        db.refresh(tenant_settings)
        # Still suspended — no double-processing
        assert tenant_settings.suspended is True


class TestStripeWebhookHandling:
    def _build_event(self, event_type: str, customer_id: str, extra: dict | None = None) -> tuple:
        """Return (payload_bytes, mock event dict)."""
        data = {"customer": customer_id, **(extra or {})}
        event = {"type": event_type, "data": {"object": data}}
        payload = json.dumps(event).encode()
        return payload, event

    def test_invoice_paid_unsuspends_tenant(self, db: Session, tenant_settings: TenantSettings):
        tenant_settings.suspended = True
        tenant_settings.grace_period_ends_at = datetime.utcnow() - timedelta(days=1)
        db.commit()

        _, event = self._build_event("invoice.paid", "cus_test123", {"period_end": 9999999999})
        with patch.object(StripeService, "_stripe") as mock_stripe:
            mock_stripe.return_value.Webhook.construct_event.return_value = event
            StripeService.handle_stripe_webhook(b"payload", "sig", db)

        db.refresh(tenant_settings)
        assert tenant_settings.suspended is False
        assert tenant_settings.grace_period_ends_at is None

    def test_payment_failed_sets_grace_period(self, db: Session, tenant_settings: TenantSettings):
        assert tenant_settings.grace_period_ends_at is None

        _, event = self._build_event("invoice.payment_failed", "cus_test123")
        with (
            patch.object(StripeService, "_stripe") as mock_stripe,
            patch.object(StripeService, "_tenant_admins", return_value=[]),
        ):
            mock_stripe.return_value.Webhook.construct_event.return_value = event
            StripeService.handle_stripe_webhook(b"payload", "sig", db)

        db.refresh(tenant_settings)
        assert tenant_settings.grace_period_ends_at is not None
        assert tenant_settings.grace_period_ends_at > datetime.utcnow()

    def test_subscription_deleted_suspends_tenant(self, db: Session, tenant_settings: TenantSettings):
        _, event = self._build_event("customer.subscription.deleted", "cus_test123", {"id": "sub_abc"})
        with (
            patch.object(StripeService, "_stripe") as mock_stripe,
            patch.object(StripeService, "_tenant_admins", return_value=[]),
        ):
            mock_stripe.return_value.Webhook.construct_event.return_value = event
            StripeService.handle_stripe_webhook(b"payload", "sig", db)

        db.refresh(tenant_settings)
        assert tenant_settings.suspended is True
        assert tenant_settings.suspension_reason == "subscription_cancelled"

    def test_unknown_customer_is_ignored(self, db: Session):
        _, event = self._build_event("invoice.paid", "cus_unknown999")
        with patch.object(StripeService, "_stripe") as mock_stripe:
            mock_stripe.return_value.Webhook.construct_event.return_value = event
            # Should not raise
            StripeService.handle_stripe_webhook(b"payload", "sig", db)
