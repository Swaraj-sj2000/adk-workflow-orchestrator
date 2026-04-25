"""
Build a role-scoped, live-data context string for the Platform Assistant LLM.
Each role only sees data it's authorised to access.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models._user import User


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _days(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    diff = (dt - _now()).days
    if diff < 0:
        return f"expired {abs(diff)}d ago"
    if diff == 0:
        return "expires today"
    return f"{diff}d remaining"


def _billing_status(ts) -> str:
    if ts.suspended:
        return "SUSPENDED"
    exp = ts.subscription_expires_at
    grace = ts.grace_period_ends_at
    if exp and exp < _now():
        if grace and grace > _now():
            return "GRACE PERIOD"
        return "EXPIRED"
    if exp and (exp - _now()).days <= 7:
        return "EXPIRING SOON"
    return "ACTIVE"


def build_context(db: Session, user: User) -> str:
    role = user.role
    try:
        if role == "platform_owner":
            return _owner_context(db)
        if role == "ceo":
            return _ceo_context(db, user)
        if role == "admin":
            return _admin_context(db, user)
        if role == "employee":
            return _employee_context(db, user)
        if role == "client":
            return _client_context(db, user)
    except Exception:
        pass
    return ""


# ── platform_owner ────────────────────────────────────────────────────────────

def _owner_context(db: Session) -> str:
    from app.models._tenant import Tenant
    from app.models._tenant_settings import TenantSettings
    from app.models._user import User
    from app.models._project import Project
    from app.models._support_ticket import SupportTicket

    tenants = db.query(Tenant).all()
    lines = ["=== PLATFORM OVERVIEW ==="]

    total = len(tenants)
    suspended_count = 0
    trial_count = 0
    paid_count = 0
    mrr_estimate = 0.0
    plan_mrr = {"trial": 0, "starter": 1000, "pro": round(5000/6), "enterprise": round(15000/12)}

    tenant_lines = []
    for t in tenants:
        ts = db.query(TenantSettings).filter_by(tenant_id=t.id).first()
        user_count = db.query(User).filter_by(tenant_id=t.id).count()
        project_count = db.query(Project).filter(
            Project.tenant_id == t.id, Project.deleted_at == None
        ).count()

        plan = ts.plan_tier if ts else "trial"
        status = _billing_status(ts) if ts else "UNKNOWN"
        exp_str = _days(ts.subscription_expires_at) if ts else "N/A"
        grace_str = ""
        if ts and ts.grace_period_ends_at and ts.grace_period_ends_at > _now():
            grace_str = f" | Grace ends: {ts.grace_period_ends_at.date()} ({_days(ts.grace_period_ends_at)})"

        if status == "SUSPENDED":
            suspended_count += 1
        if plan == "trial":
            trial_count += 1
        else:
            paid_count += 1
            mrr_estimate += plan_mrr.get(plan, 0)

        tenant_lines.append(
            f"- {t.name} | Plan: {plan.upper()} | Status: {status} | "
            f"Subscription: {exp_str} | Users: {user_count} | Projects: {project_count}"
            + grace_str
        )

    lines.append(f"Total tenants: {total} | Active: {total - suspended_count} | Suspended: {suspended_count}")
    lines.append(f"Trial: {trial_count} | Paid: {paid_count} | Estimated MRR: ₹{mrr_estimate:,.0f}")
    lines.append("")
    lines.append("TENANT DETAILS:")
    lines.extend(tenant_lines)

    # Open support tickets
    tickets = db.query(SupportTicket).filter_by(status="open").order_by(
        SupportTicket.created_at.desc()
    ).limit(10).all()
    if tickets:
        lines.append("")
        lines.append(f"OPEN SUPPORT TICKETS ({len(tickets)}):")
        for tk in tickets:
            tenant = db.query(Tenant).filter_by(id=tk.tenant_id).first()
            company = tenant.name if tenant else f"Tenant#{tk.tenant_id}"
            lines.append(f"- [{tk.priority.upper()}] {tk.subject} — from {company} (#{tk.id})")

    return "\n".join(lines)


# ── ceo ───────────────────────────────────────────────────────────────────────

def _ceo_context(db: Session, user: User) -> str:
    from app.models._project import Project
    from app.models._task import Task
    from app.models._user import User as UserModel
    from app.models._employee_profile import EmployeeProfile
    from app.models._tenant_settings import TenantSettings
    from app.models._tenant import Tenant
    from app.models._decision_log import DecisionLog

    tid = user.tenant_id
    lines = []

    tenant = db.query(Tenant).filter_by(id=tid).first()
    ts = db.query(TenantSettings).filter_by(tenant_id=tid).first()
    lines.append(f"=== COMPANY: {tenant.name if tenant else 'Your Company'} ===")

    if ts:
        status = _billing_status(ts)
        lines.append(
            f"Plan: {ts.plan_tier.upper()} | Billing: {status} | "
            f"Subscription: {_days(ts.subscription_expires_at)}"
        )

    # Projects
    projects = db.query(Project).filter(
        Project.tenant_id == tid, Project.deleted_at == None
    ).all()
    total_budget = sum(p.budget or 0 for p in projects)
    total_spent = sum(p.spent or 0 for p in projects)
    active = [p for p in projects if p.status in ("planning", "in-progress", "on-hold")]
    completed = [p for p in projects if p.status == "completed"]

    lines.append(f"\nPROJECTS: {len(projects)} total | {len(active)} active | {len(completed)} completed")
    lines.append(f"Budget: ₹{total_budget:,.0f} allocated | ₹{total_spent:,.0f} spent")

    for p in projects[:15]:
        deadline_str = f" | Deadline: {p.deadline.date()}" if p.deadline else ""
        lines.append(
            f"  • {p.name} [{p.status}] {p.progress}% complete | "
            f"₹{p.spent:,.0f}/₹{p.budget:,.0f} spent{deadline_str}"
        )

    # Team
    emp_count = db.query(EmployeeProfile).filter(
        EmployeeProfile.tenant_id == tid, EmployeeProfile.deleted_at == None
    ).count()
    lines.append(f"\nTEAM: {emp_count} employees")

    # Recent AI risk decisions
    risk_decisions = db.query(DecisionLog).filter(
        DecisionLog.decision_type.in_(["risk", "escalation", "reassignment"])
    ).order_by(DecisionLog.created_at.desc()).limit(5).all()
    if risk_decisions:
        lines.append("\nRECENT AI RISK / ESCALATION DECISIONS:")
        for d in risk_decisions:
            lines.append(
                f"  • [{d.decision_type}] {d.decision_taken[:120]} "
                f"(confidence: {int((d.confidence or 0)*100)}%)"
            )

    return "\n".join(lines)


# ── admin ─────────────────────────────────────────────────────────────────────

def _admin_context(db: Session, user: User) -> str:
    from app.models._project import Project
    from app.models._task import Task
    from app.models._user import User as UserModel
    from app.models._employee_profile import EmployeeProfile
    from app.models._decision_log import DecisionLog
    from app.models._tenant import Tenant
    from app.models._tenant_settings import TenantSettings

    tid = user.tenant_id
    lines = []

    tenant = db.query(Tenant).filter_by(id=tid).first()
    ts = db.query(TenantSettings).filter_by(tenant_id=tid).first()
    lines.append(f"=== COMPANY: {tenant.name if tenant else 'Your Company'} ===")
    if ts:
        lines.append(f"Plan: {ts.plan_tier.upper()} | Status: {_billing_status(ts)}")

    # Projects
    projects = db.query(Project).filter(
        Project.tenant_id == tid, Project.deleted_at == None
    ).all()
    lines.append(f"\nPROJECTS ({len(projects)}):")
    for p in projects[:20]:
        task_total = db.query(Task).filter(
            Task.project_id == p.id, Task.deleted_at == None
        ).count()
        task_done = db.query(Task).filter(
            Task.project_id == p.id, Task.status == "completed", Task.deleted_at == None
        ).count()
        task_blocked = db.query(Task).filter(
            Task.project_id == p.id, Task.status == "blocked", Task.deleted_at == None
        ).count()
        deadline_str = f" | Due: {p.deadline.date()}" if p.deadline else ""
        lines.append(
            f"  • {p.name} [{p.status}] {p.progress}% | "
            f"Tasks: {task_done}/{task_total} done, {task_blocked} blocked"
            f"{deadline_str} | Budget: ₹{p.spent:,.0f}/₹{p.budget:,.0f}"
        )

    # Team
    employees = db.query(EmployeeProfile, UserModel).join(
        UserModel, EmployeeProfile.user_id == UserModel.id
    ).filter(
        EmployeeProfile.tenant_id == tid, EmployeeProfile.deleted_at == None
    ).all()
    lines.append(f"\nTEAM ({len(employees)} employees):")
    for ep, u in employees[:20]:
        skills_str = ", ".join(list((ep.skills or {}).keys())[:5])
        load_pct = int((ep.current_load / ep.max_capacity * 100) if ep.max_capacity else 0)
        lines.append(
            f"  • {u.full_name or u.email} [{ep.availability_status}] "
            f"Load: {load_pct}% | Skills: {skills_str or 'none set'}"
        )

    # Recent AI decisions
    decisions = db.query(DecisionLog).order_by(
        DecisionLog.created_at.desc()
    ).limit(5).all()
    if decisions:
        lines.append("\nRECENT AI DECISIONS:")
        for d in decisions:
            lines.append(
                f"  • [{d.decision_type}] {d.decision_taken[:120]} "
                f"(confidence: {int((d.confidence or 0)*100)}%)"
            )

    return "\n".join(lines)


# ── employee ──────────────────────────────────────────────────────────────────

def _employee_context(db: Session, user: User) -> str:
    from app.models._employee_profile import EmployeeProfile
    from app.models._task_assignment import TaskAssignment
    from app.models._task import Task
    from app.models._project import Project

    ep = db.query(EmployeeProfile).filter_by(user_id=user.id).first()
    lines = [f"=== YOUR PROFILE ==="]

    if ep:
        skills_str = ", ".join(f"{k} ({int(v*100)}%)" for k, v in (ep.skills or {}).items())
        load_pct = int((ep.current_load / ep.max_capacity * 100) if ep.max_capacity else 0)
        lines.append(
            f"Skills: {skills_str or 'none set'} | "
            f"Workload: {ep.current_load:.1f}h/{ep.max_capacity:.1f}h ({load_pct}%) | "
            f"Status: {ep.availability_status}"
        )

    # Assigned tasks
    assignments = db.query(TaskAssignment).filter(
        TaskAssignment.employee_id == (ep.id if ep else -1),
        TaskAssignment.status.in_(["assigned", "in-progress"])
    ).all()

    if assignments:
        lines.append(f"\nYOUR ASSIGNED TASKS ({len(assignments)}):")
        for a in assignments:
            task = db.query(Task).filter_by(id=a.task_id).first()
            if not task or task.deleted_at:
                continue
            project = db.query(Project).filter_by(id=task.project_id).first()
            proj_name = project.name if project else "Unknown project"
            deadline_str = f" | Due: {task.deadline.date()}" if task.deadline else ""
            lines.append(
                f"  • [{task.urgency.upper()}] {task.description[:80]} "
                f"— {proj_name} | Status: {task.status}{deadline_str}"
            )
    else:
        lines.append("\nNo tasks currently assigned to you.")

    # Projects
    project_ids = set()
    for a in assignments:
        t = db.query(Task).filter_by(id=a.task_id).first()
        if t:
            project_ids.add(t.project_id)
    if project_ids:
        lines.append(f"\nYOUR PROJECTS:")
        for pid in list(project_ids)[:10]:
            p = db.query(Project).filter_by(id=pid).first()
            if p:
                lines.append(f"  • {p.name} [{p.status}] {p.progress}% complete")

    return "\n".join(lines)


# ── client ────────────────────────────────────────────────────────────────────

def _client_context(db: Session, user: User) -> str:
    from app.models._client_profile import ClientProfile
    from app.models._project import Project
    from app.models._task import Task

    cp = db.query(ClientProfile).filter_by(user_id=user.id).first()
    lines = [f"=== YOUR CLIENT PROFILE ==="]
    if cp:
        lines.append(f"Company: {cp.company_name}")

    projects = db.query(Project).filter(
        Project.client_id == (cp.id if cp else -1),
        Project.deleted_at == None
    ).all()

    if projects:
        lines.append(f"\nYOUR PROJECTS ({len(projects)}):")
        for p in projects:
            task_total = db.query(Task).filter(
                Task.project_id == p.id, Task.deleted_at == None
            ).count()
            task_done = db.query(Task).filter(
                Task.project_id == p.id, Task.status == "completed", Task.deleted_at == None
            ).count()
            deadline_str = f" | Due: {p.deadline.date()}" if p.deadline else ""
            budget_str = f" | Budget: ₹{p.budget:,.0f} (₹{p.spent:,.0f} spent)" if p.budget else ""
            lines.append(
                f"  • {p.name} [{p.status}] {p.progress}% complete | "
                f"Tasks: {task_done}/{task_total} done{deadline_str}{budget_str}"
            )
    else:
        lines.append("\nNo projects associated with your account yet.")

    return "\n".join(lines)
