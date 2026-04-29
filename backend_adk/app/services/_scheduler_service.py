from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core._logging import get_logger
from app.models._agent_run import AgentRun
from app.models._audit_log import AuditLog
from app.models._decision_log import DecisionLog
from app.models._email_delivery_log import EmailDeliveryLog
from app.models._employee_profile import EmployeeProfile
from app.models._notification import Notification
from app.models._platform_audit_log import PlatformAuditLog
from app.models._project import Project
from app.models._scheduled_agent_job import ScheduledAgentJob
from app.models._tenant import Tenant
from app.models._user import User
from app.models._workflow_run import WorkflowRun
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
            if token.startswith("*/"):
                return value % int(token[2:]) == 0
            if "," in token:
                return value in {int(t) for t in token.split(",")}
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

            elif job.job_type == "archive_old_runs":
                cls._archive_old_workflow_runs(db)

            elif job.job_type == "health_alerts":
                cls._run_health_alerts(db, job.tenant_id)

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
    def _archive_old_workflow_runs(cls, db: Session, retention_days: int = 90) -> None:
        """
        Purge old log records to prevent unbounded DB growth.

        Retention policy (conservative — keeps recent data for debugging):
          workflow_runs + agent_runs  : 90 days  (completed/failed only)
          decision_logs               : 90 days
          audit_log                   : 90 days
          email_delivery_logs         : 60 days  (sent/failed only)
          platform_audit_logs         : 180 days (longer for compliance)
        """
        total_deleted = 0

        # ── workflow_runs + their agent_runs (must delete children first) ──
        wf_cutoff = cls._now_utc() - timedelta(days=retention_days)
        old_runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.created_at < wf_cutoff, WorkflowRun.status.in_(["completed", "failed"]))
            .all()
        )
        run_ids = [r.id for r in old_runs]
        if run_ids:
            deleted = db.query(AgentRun).filter(AgentRun.workflow_run_id.in_(run_ids)).delete(synchronize_session=False)
            db.query(WorkflowRun).filter(WorkflowRun.id.in_(run_ids)).delete(synchronize_session=False)
            total_deleted += len(run_ids)
            logger.info("Purged %d workflow runs + %d agent runs (cutoff=%s)", len(run_ids), deleted, wf_cutoff.date())

        # ── decision_logs ──
        dl_cutoff = cls._now_utc() - timedelta(days=retention_days)
        deleted = db.query(DecisionLog).filter(DecisionLog.created_at < dl_cutoff).delete(synchronize_session=False)
        if deleted:
            total_deleted += deleted
            logger.info("Purged %d decision_logs (cutoff=%s)", deleted, dl_cutoff.date())

        # ── audit_log ──
        al_cutoff = cls._now_utc() - timedelta(days=retention_days)
        deleted = db.query(AuditLog).filter(AuditLog.timestamp < al_cutoff).delete(synchronize_session=False)
        if deleted:
            total_deleted += deleted
            logger.info("Purged %d audit_log rows (cutoff=%s)", deleted, al_cutoff.date())

        # ── email_delivery_logs (60 days, sent/failed only) ──
        email_cutoff = cls._now_utc() - timedelta(days=60)
        deleted = (
            db.query(EmailDeliveryLog)
            .filter(EmailDeliveryLog.created_at < email_cutoff, EmailDeliveryLog.status.in_(["sent", "failed", "delivered"]))
            .delete(synchronize_session=False)
        )
        if deleted:
            total_deleted += deleted
            logger.info("Purged %d email_delivery_logs (cutoff=%s)", deleted, email_cutoff.date())

        # ── platform_audit_logs (180 days) ──
        pal_cutoff = cls._now_utc() - timedelta(days=180)
        deleted = db.query(PlatformAuditLog).filter(PlatformAuditLog.timestamp < pal_cutoff).delete(synchronize_session=False)
        if deleted:
            total_deleted += deleted
            logger.info("Purged %d platform_audit_logs (cutoff=%s)", deleted, pal_cutoff.date())

        db.commit()
        logger.info("Log purge complete — total rows removed: %d", total_deleted)

    @classmethod
    def _run_health_alerts(cls, db: Session, tenant_id: int) -> None:
        now = cls._now_utc()
        cutoff_24h = now - timedelta(hours=24)

        def _throttled(user_id: int, ref_type: str) -> bool:
            return (
                db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.tenant_id == tenant_id,
                    Notification.reference_type == ref_type,
                    Notification.created_at >= cutoff_24h,
                )
                .first()
            ) is not None

        def _alert(user_id: int, ntype: str, title: str, body: str, ref_type: str) -> None:
            if _throttled(user_id, ref_type):
                return
            db.add(Notification(
                tenant_id=tenant_id, user_id=user_id,
                type=ntype, title=title, body=body,
                reference_type=ref_type, reference_id=None,
            ))

        # ── CEO: at-risk / delayed projects ────────────────────────────────────
        ceo = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.role == "ceo",
            User.deleted_at.is_(None),
        ).first()

        if ceo:
            at_risk = db.query(Project).filter(
                Project.tenant_id == tenant_id,
                Project.deleted_at.is_(None),
                Project.status.in_(["at_risk", "delayed"]),
            ).all()
            if at_risk:
                names = ", ".join(p.name for p in at_risk[:3])
                suffix = f" (+{len(at_risk) - 3} more)" if len(at_risk) > 3 else ""
                _alert(
                    ceo.id, "escalation",
                    f"{len(at_risk)} project(s) need your attention",
                    f"At-risk or delayed: {names}{suffix}. Review delivery timelines.",
                    "health_alert_ceo_risk",
                )

        # ── Admin: team leave coverage ──────────────────────────────────────────
        admins = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.role == "admin",
            User.deleted_at.is_(None),
        ).all()

        for admin in admins:
            admin_profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == admin.id,
                EmployeeProfile.tenant_id == tenant_id,
                EmployeeProfile.deleted_at.is_(None),
            ).first()
            if not admin_profile:
                continue

            team = db.query(EmployeeProfile).filter(
                EmployeeProfile.tenant_id == tenant_id,
                EmployeeProfile.manager_id == admin_profile.id,
                EmployeeProfile.deleted_at.is_(None),
            ).all()

            if not team:
                continue

            on_leave = [ep for ep in team if getattr(ep, "availability_status", "") == "on-leave"]
            if on_leave and len(on_leave) / len(team) >= 0.5:
                _alert(
                    admin.id, "escalation",
                    f"{len(on_leave)} of {len(team)} team members on leave",
                    "More than half your team is on leave simultaneously. Project delivery may be at risk.",
                    "health_alert_admin_leave",
                )

        db.commit()
        logger.info("Health alert check complete for tenant_id=%s", tenant_id)

    @classmethod
    def seed_default_jobs_for_tenant(cls, db: Session, tenant_id: int) -> None:
        default_jobs = [
            {"job_type": "weekly_digest", "cron_expr": "0 9 * * 1"},
            {"job_type": "payment_check", "cron_expr": "0 0 * * *"},
            {"job_type": "archive_old_runs", "cron_expr": "0 3 * * 0"},
            {"job_type": "health_alerts", "cron_expr": "0 */6 * * *"},
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
