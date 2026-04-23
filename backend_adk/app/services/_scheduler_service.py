from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core._logging import get_logger
from app.models._project import Project
from app.models._scheduled_agent_job import ScheduledAgentJob
from app.models._tenant import Tenant
from app.models._user import User
from app.services._ceo_service import CEOService
from app.services._email_service import EmailService
from app.services._multi_agent_orchestrator import MultiAgentOrchestrator
from app.services._stripe_service import StripeService


logger = get_logger(__name__)


class SchedulerService:
    @staticmethod
    def _now_utc() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _parse_cron(expr: str) -> tuple[str, str, str, str, str]:
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expr}")
        return tuple(parts)  # type: ignore[return-value]

    @staticmethod
    def _weekday_for_cron(dt: datetime) -> int:
        return (dt.weekday() + 1) % 7

    @classmethod
    def _cron_matches(cls, dt: datetime, expr: str) -> bool:
        minute, hour, day, month, weekday = cls._parse_cron(expr)

        def _matches(value: int, token: str) -> bool:
            if token == "*":
                return True
            return value == int(token)

        return (
            _matches(dt.minute, minute)
            and _matches(dt.hour, hour)
            and _matches(dt.day, day)
            and _matches(dt.month, month)
            and _matches(cls._weekday_for_cron(dt), "0" if weekday == "7" else weekday)
        )

    @classmethod
    def _next_run_at(cls, cron_expr: str, timezone_name: str, base_time: datetime | None = None) -> datetime:
        tz = ZoneInfo(timezone_name or "UTC")
        local_base = (base_time or datetime.now(timezone.utc)).replace(tzinfo=timezone.utc).astimezone(tz)
        candidate = local_base.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(60 * 24 * 400):
            if cls._cron_matches(candidate, cron_expr):
                return candidate.astimezone(timezone.utc).replace(tzinfo=None)
            candidate += timedelta(minutes=1)
        raise ValueError(f"Unable to compute next run for cron '{cron_expr}'")

    @classmethod
    async def run_scheduler_loop(cls, db_factory) -> None:
        logger.info("Scheduler loop started")
        try:
            while True:
                db = db_factory()
                try:
                    now = cls._now_utc()
                    jobs = (
                        db.query(ScheduledAgentJob)
                        .filter(ScheduledAgentJob.enabled.is_(True))
                        .all()
                    )
                    for job in jobs:
                        if job.next_run_at and job.next_run_at > now:
                            continue
                        await cls._run_job(db, job)
                finally:
                    db.close()
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
            raise

    @classmethod
    async def _run_job(cls, db: Session, job: ScheduledAgentJob) -> None:
        try:
            logger.info("Running scheduled job job_id=%s type=%s", job.id, job.job_type)
            if job.job_type == "nightly_observer" and job.project_id:
                project = db.query(Project).filter(Project.id == job.project_id, Project.tenant_id == job.tenant_id).first()
                if project:
                    workflow = MultiAgentOrchestrator(db).run_project_execution_loop(
                        project_id=project.id,
                        requested_by=project.admin_id,
                        persist_followup_messages=True,
                    )
                    risk_level = (
                        ((workflow.final_output or {}).get("delivery_review") or {})
                        .get("risk_summary", {})
                        .get("risk_level")
                    )
                    if risk_level in {"high", "critical"}:
                        recipients = (
                            db.query(User)
                            .filter(User.tenant_id == job.tenant_id, User.role.in_(["admin", "ceo"]))
                            .all()
                        )
                        for recipient in recipients:
                            EmailService.send_escalation_alert_email(
                                to_email=recipient.email,
                                recipient_name=recipient.full_name or recipient.email,
                                project_name=project.name,
                                reason=f"Scheduled observer detected {risk_level} delivery risk.",
                                workflow_run_id=workflow.id,
                            )

            elif job.job_type == "weekly_digest":
                overview = CEOService.get_company_overview(db, job.tenant_id)
                financials = CEOService.get_financial_overview(db, job.tenant_id)
                risks = CEOService.get_risk_flags(db, job.tenant_id)
                recipients = (
                    db.query(User)
                    .filter(User.tenant_id == job.tenant_id, User.role.in_(["admin", "ceo"]))
                    .all()
                )
                digest_data = {
                    "projects_on_track": overview.get("projects_on_track", 0),
                    "projects_at_risk": overview.get("projects_at_risk", 0),
                    "projects_delayed": overview.get("projects_delayed", 0),
                    "total_tasks_completed": overview.get("projects_completed", 0),
                    "blockers_open": overview.get("active_blockers", 0),
                    "top_risks": [risk.get("message") for risk in risks[:5]],
                    "outstanding": financials.get("total_outstanding", 0.0),
                }
                for recipient in recipients:
                    EmailService.send_weekly_digest_email(
                        to_email=recipient.email,
                        recipient_name=recipient.full_name or recipient.email,
                        digest_data=digest_data,
                    )

            elif job.job_type == "payment_check":
                StripeService.check_and_enforce_grace_periods(db)

            job.last_run_at = cls._now_utc()
            job.last_status = "success"
            job.last_error = None
        except Exception as exc:
            job.last_run_at = cls._now_utc()
            job.last_status = "failed"
            job.last_error = str(exc)
            logger.error("Scheduled job failed job_id=%s error=%s", job.id, exc, exc_info=True)
        finally:
            job.next_run_at = cls._next_run_at(job.cron_expr, job.timezone)
            db.add(job)
            db.commit()

    @classmethod
    def seed_default_jobs_for_tenant(cls, db: Session, tenant_id: int) -> None:
        default_jobs = [
            {"job_type": "weekly_digest", "cron_expr": "0 9 * * 1"},
            {"job_type": "payment_check", "cron_expr": "0 0 * * *"},
        ]
        for job_spec in default_jobs:
            existing = (
                db.query(ScheduledAgentJob)
                .filter(
                    ScheduledAgentJob.tenant_id == tenant_id,
                    ScheduledAgentJob.job_type == job_spec["job_type"],
                    ScheduledAgentJob.project_id.is_(None),
                )
                .first()
            )
            if existing:
                continue
            db.add(
                ScheduledAgentJob(
                    tenant_id=tenant_id,
                    project_id=None,
                    job_type=job_spec["job_type"],
                    cron_expr=job_spec["cron_expr"],
                    timezone="UTC",
                    enabled=True,
                    next_run_at=cls._next_run_at(job_spec["cron_expr"], "UTC"),
                )
            )

        projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
        for project in projects:
            existing = (
                db.query(ScheduledAgentJob)
                .filter(
                    ScheduledAgentJob.tenant_id == tenant_id,
                    ScheduledAgentJob.project_id == project.id,
                    ScheduledAgentJob.job_type == "nightly_observer",
                )
                .first()
            )
            if existing:
                continue
            db.add(
                ScheduledAgentJob(
                    tenant_id=tenant_id,
                    project_id=project.id,
                    job_type="nightly_observer",
                    cron_expr="0 2 * * *",
                    timezone="UTC",
                    enabled=True,
                    next_run_at=cls._next_run_at("0 2 * * *", "UTC"),
                )
            )
        db.commit()

    @classmethod
    def seed_default_jobs_for_existing_tenants(cls, db: Session) -> None:
        tenants = db.query(Tenant).all()
        for tenant in tenants:
            cls.seed_default_jobs_for_tenant(db, tenant.id)
