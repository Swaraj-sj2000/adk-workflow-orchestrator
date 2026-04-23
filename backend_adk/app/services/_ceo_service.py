from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models._blocker import Blocker
from app.models._client_profile import ClientProfile
from app.models._communication import Communication
from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._task import Task
from app.models._team import Team, TeamMember
from app.models._user import User


PAYMENT_COLLECTED_STATUSES = {"client-confirmed", "admin-confirmed", "completed"}
PAYMENT_INVOICED_STATUSES = {"partial", "client-confirmed", "admin-confirmed", "completed", "disputed"}
PAYMENT_STATUS_PRIORITY = {
    "disputed": 5,
    "pending": 4,
    "partial": 3,
    "client-confirmed": 2,
    "admin-confirmed": 1,
    "completed": 0,
}


class CEOService:
    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return max(0.0, min(1.0, numerator / denominator))

    @classmethod
    def _expected_progress(cls, project: Project) -> float:
        if not project.start_date or not project.deadline or project.deadline <= project.start_date:
            return 0.0

        now = cls._now()
        total_duration = (project.deadline - project.start_date).total_seconds()
        elapsed = (min(now, project.deadline) - project.start_date).total_seconds()
        if total_duration <= 0:
            return 0.0
        return max(0.0, min(100.0, (elapsed / total_duration) * 100.0))

    @classmethod
    def _is_project_delayed(cls, project: Project) -> bool:
        return bool(project.deadline and project.deadline < cls._now() and project.status != "completed")

    @classmethod
    def _is_project_at_risk(cls, project: Project, blocker_count: int) -> bool:
        if cls._is_project_delayed(project):
            return True
        if blocker_count > 0:
            return True
        expected_progress = cls._expected_progress(project)
        return expected_progress > 0 and float(project.progress or 0) + 10 < expected_progress

    @classmethod
    def _is_project_on_track(cls, project: Project, blocker_count: int) -> bool:
        if project.status == "completed":
            return False
        if cls._is_project_delayed(project) or blocker_count > 0:
            return False
        expected_progress = cls._expected_progress(project)
        if expected_progress == 0:
            return True
        return float(project.progress or 0) + 10 >= expected_progress

    @staticmethod
    def _project_blockers(db: Session, tenant_id: int) -> Dict[int, List[Blocker]]:
        rows = (
            db.query(Blocker, Task.project_id)
            .join(Task, Task.id == Blocker.task_id)
            .join(Project, Project.id == Task.project_id)
            .filter(Project.tenant_id == tenant_id)
            .all()
        )
        blockers_by_project: Dict[int, List[Blocker]] = {}
        for blocker, project_id in rows:
            blockers_by_project.setdefault(project_id, []).append(blocker)
        return blockers_by_project

    @classmethod
    def get_company_overview(cls, db: Session, tenant_id: int | None) -> dict:
        if tenant_id is None:
            return {
                "total_projects": 0,
                "projects_on_track": 0,
                "projects_at_risk": 0,
                "projects_delayed": 0,
                "projects_completed": 0,
                "total_employees": 0,
                "employees_available": 0,
                "employees_overloaded": 0,
                "total_clients": 0,
                "active_blockers": 0,
                "health_score": 0.0,
            }
        projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
        employees = db.query(EmployeeProfile).filter(EmployeeProfile.tenant_id == tenant_id).all()
        clients = db.query(ClientProfile).filter(ClientProfile.tenant_id == tenant_id).all()
        blockers_by_project = cls._project_blockers(db, tenant_id)

        projects_on_track = 0
        projects_at_risk = 0
        projects_delayed = 0
        projects_completed = 0

        for project in projects:
            project_blockers = [b for b in blockers_by_project.get(project.id, []) if b.status == "open"]
            blocker_count = len(project_blockers)
            if project.status == "completed":
                projects_completed += 1
            if cls._is_project_delayed(project):
                projects_delayed += 1
            elif cls._is_project_at_risk(project, blocker_count):
                projects_at_risk += 1
            elif cls._is_project_on_track(project, blocker_count):
                projects_on_track += 1

        employees_available = sum(1 for employee in employees if employee.availability_status == "available")
        employees_overloaded = sum(
            1
            for employee in employees
            if (employee.current_load or 0) > 0.8 * (employee.max_capacity or 1)
        )

        active_blockers = sum(
            1
            for blockers in blockers_by_project.values()
            for blocker in blockers
            if blocker.status == "open"
        )

        on_track_ratio = cls._safe_ratio(projects_on_track, len(projects) or 1)
        balanced_employees = sum(
            1
            for employee in employees
            if (employee.max_capacity or 0) > 0 and (employee.current_load or 0) <= 0.8 * employee.max_capacity
        )
        utilization_balance = cls._safe_ratio(balanced_employees, len(employees) or 1)

        invoiced_total = sum(float(project.budget or 0.0) for project in projects if project.payment_status in PAYMENT_INVOICED_STATUSES)
        collected_total = sum(float(project.budget or 0.0) for project in projects if project.payment_status in PAYMENT_COLLECTED_STATUSES)
        payment_collection_ratio = cls._safe_ratio(collected_total, invoiced_total or 1.0)

        return {
            "total_projects": len(projects),
            "projects_on_track": projects_on_track,
            "projects_at_risk": projects_at_risk,
            "projects_delayed": projects_delayed,
            "projects_completed": projects_completed,
            "total_employees": len(employees),
            "employees_available": employees_available,
            "employees_overloaded": employees_overloaded,
            "total_clients": len(clients),
            "active_blockers": active_blockers,
            "health_score": round(
                on_track_ratio * 40 + utilization_balance * 30 + payment_collection_ratio * 30,
                2,
            ),
        }

    @classmethod
    def get_financial_overview(cls, db: Session, tenant_id: int | None) -> dict:
        if tenant_id is None:
            return {
                "total_budget_across_projects": 0.0,
                "total_spent": 0.0,
                "total_invoiced": 0.0,
                "total_collected": 0.0,
                "total_outstanding": 0.0,
                "overdue_payments": [],
                "per_project_pl": [],
            }
        projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
        overdue_payments = []
        per_project_pl = []
        now = cls._now()

        total_budget = sum(float(project.budget or 0.0) for project in projects)
        total_spent = sum(float(project.spent or 0.0) for project in projects)
        total_invoiced = sum(
            float(project.budget or 0.0)
            for project in projects
            if project.payment_status in PAYMENT_INVOICED_STATUSES
        )
        total_collected = sum(
            float(project.budget or 0.0)
            for project in projects
            if project.payment_status in PAYMENT_COLLECTED_STATUSES
        )

        for project in projects:
            budget = float(project.budget or 0.0)
            spent = float(project.spent or 0.0)
            profit_margin = ((budget - spent) / budget * 100.0) if budget > 0 else 0.0
            per_project_pl.append(
                {
                    "project_id": project.id,
                    "project_name": project.name,
                    "budget": round(budget, 2),
                    "spent": round(spent, 2),
                    "status": project.status,
                    "payment_status": project.payment_status,
                    "profit_margin": round(profit_margin, 2),
                }
            )

            if (
                project.client
                and project.completed_at
                and project.completed_at < now - timedelta(days=30)
                and project.payment_status in {"pending", "partial"}
            ):
                overdue_payments.append(
                    {
                        "client_name": project.client.company_name,
                        "project_name": project.name,
                        "amount": round(budget, 2),
                        "days_overdue": (now - project.completed_at).days,
                        "payment_status": project.payment_status,
                    }
                )

        return {
            "total_budget_across_projects": round(total_budget, 2),
            "total_spent": round(total_spent, 2),
            "total_invoiced": round(total_invoiced, 2),
            "total_collected": round(total_collected, 2),
            "total_outstanding": round(total_invoiced - total_collected, 2),
            "overdue_payments": overdue_payments,
            "per_project_pl": sorted(per_project_pl, key=lambda row: row["profit_margin"]),
        }

    @classmethod
    def get_team_utilization(cls, db: Session, tenant_id: int | None) -> dict:
        if tenant_id is None:
            return {
                "overall_utilization_pct": 0.0,
                "teams": [],
                "top_performers": [],
            }
        teams = db.query(Team).filter(Team.tenant_id == tenant_id).all()
        blockers_by_project = cls._project_blockers(db, tenant_id)

        project_lookup = {project.id: project for project in db.query(Project).filter(Project.tenant_id == tenant_id).all()}
        assignments = db.query(TeamMember).filter(TeamMember.tenant_id == tenant_id, TeamMember.status == "active").all()
        team_members: Dict[int, List[TeamMember]] = {}
        for member in assignments:
            team_members.setdefault(member.team_id, []).append(member)

        employee_lookup = {
            employee.id: employee
            for employee in db.query(EmployeeProfile).filter(EmployeeProfile.tenant_id == tenant_id).all()
        }

        teams_payload = []
        all_utilization_values = []
        for team in teams:
            members = team_members.get(team.id, [])
            utilizations = []
            overloaded = 0
            available = 0
            for member in members:
                if not member.employee_profile_id or member.employee_profile_id not in employee_lookup:
                    continue
                employee = employee_lookup[member.employee_profile_id]
                utilization = cls._safe_ratio(float(employee.current_load or 0.0), float(employee.max_capacity or 0.0)) * 100
                utilizations.append(utilization)
                all_utilization_values.append(utilization)
                if (employee.current_load or 0) > 0.8 * (employee.max_capacity or 1):
                    overloaded += 1
                if employee.availability_status == "available":
                    available += 1

            project = project_lookup.get(team.project_id)
            active_blockers = sum(
                1
                for blocker in blockers_by_project.get(team.project_id, [])
                if blocker.status == "open"
            )
            teams_payload.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "project_name": project.name if project else "Unknown Project",
                    "member_count": len(members),
                    "avg_utilization_pct": round(sum(utilizations) / len(utilizations), 2) if utilizations else 0.0,
                    "overloaded_members": overloaded,
                    "available_members": available,
                    "active_blockers": active_blockers,
                }
            )

        top_performers = []
        metrics_rows = (
            db.query(EmployeeMetrics, EmployeeProfile, User)
            .join(EmployeeProfile, EmployeeProfile.id == EmployeeMetrics.employee_id)
            .join(User, User.id == EmployeeProfile.user_id)
            .filter(EmployeeProfile.tenant_id == tenant_id)
            .all()
        )
        ranked = sorted(
            metrics_rows,
            key=lambda row: float(row[0].efficiency_score or 0.0) * float(row[0].reliability_score or 0.0),
            reverse=True,
        )
        for metrics, _employee, user in ranked[:3]:
            top_performers.append(
                {
                    "employee_name": user.full_name or user.email,
                    "efficiency": round(float(metrics.efficiency_score or 0.0), 2),
                    "reliability": round(float(metrics.reliability_score or 0.0), 2),
                    "tasks_completed": int(metrics.total_tasks_completed or 0),
                }
            )

        return {
            "overall_utilization_pct": round(sum(all_utilization_values) / len(all_utilization_values), 2) if all_utilization_values else 0.0,
            "teams": teams_payload,
            "top_performers": top_performers,
        }

    @classmethod
    def get_client_status(cls, db: Session, tenant_id: int | None) -> list:
        if tenant_id is None:
            return []
        clients = db.query(ClientProfile).filter(ClientProfile.tenant_id == tenant_id).all()
        projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
        communications = db.query(Communication).join(Project, Project.id == Communication.project_id).filter(Project.tenant_id == tenant_id).all()
        now = cls._now()

        projects_by_client: Dict[int, List[Project]] = {}
        for project in projects:
            if project.client_id:
                projects_by_client.setdefault(project.client_id, []).append(project)

        last_communication_by_client: Dict[int, datetime] = {}
        project_to_client = {project.id: project.client_id for project in projects if project.client_id}
        for communication in communications:
            client_id = project_to_client.get(communication.project_id)
            if not client_id:
                continue
            last_sent = last_communication_by_client.get(client_id)
            if last_sent is None or (communication.sent_at and communication.sent_at > last_sent):
                last_communication_by_client[client_id] = communication.sent_at

        payload = []
        for client in clients:
            client_projects = projects_by_client.get(client.id, [])
            total_billed = sum(float(project.budget or 0.0) for project in client_projects if project.payment_status in PAYMENT_INVOICED_STATUSES)
            total_paid = sum(float(project.budget or 0.0) for project in client_projects if project.payment_status in PAYMENT_COLLECTED_STATUSES)
            worst_payment_status = "completed"
            for project in client_projects:
                if PAYMENT_STATUS_PRIORITY.get(project.payment_status, 0) > PAYMENT_STATUS_PRIORITY.get(worst_payment_status, 0):
                    worst_payment_status = project.payment_status

            overdue_days = max(
                (
                    (now - project.completed_at).days
                    for project in client_projects
                    if project.completed_at and project.payment_status in {"pending", "partial"}
                ),
                default=0,
            )
            risk_flag = None
            if overdue_days >= 60:
                risk_flag = "overdue_60d"
            elif overdue_days >= 30:
                risk_flag = "overdue_30d"
            elif any(cls._is_project_at_risk(project, 0) for project in client_projects):
                risk_flag = "at_risk"

            payload.append(
                {
                    "client_id": client.id,
                    "company_name": client.company_name,
                    "contact_person": client.contact_person,
                    "active_projects": sum(1 for project in client_projects if project.status not in {"completed", "cancelled"}),
                    "completed_projects": sum(1 for project in client_projects if project.status == "completed"),
                    "total_billed": round(total_billed, 2),
                    "total_paid": round(total_paid, 2),
                    "outstanding": round(total_billed - total_paid, 2),
                    "payment_status": worst_payment_status,
                    "last_communication_at": last_communication_by_client.get(client.id).isoformat()
                    if last_communication_by_client.get(client.id)
                    else None,
                    "risk_flag": risk_flag,
                }
            )

        return payload

    @classmethod
    def get_risk_flags(cls, db: Session, tenant_id: int | None) -> list:
        if tenant_id is None:
            return []
        now = cls._now()
        projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
        employees = db.query(EmployeeProfile).filter(EmployeeProfile.tenant_id == tenant_id).all()
        clients = db.query(ClientProfile).filter(ClientProfile.tenant_id == tenant_id).all()
        blockers_by_project = cls._project_blockers(db, tenant_id)
        projects_by_client = {}
        for project in projects:
            if project.client_id:
                projects_by_client.setdefault(project.client_id, []).append(project)

        risk_flags: List[Dict[str, Any]] = []

        for project in projects:
            if project.deadline and project.deadline < now and project.status != "completed":
                days_late = (now - project.deadline).days
                risk_flags.append(
                    {
                        "type": "delayed_project",
                        "severity": "critical" if days_late > 7 else "high",
                        "message": f"{project.name} is past deadline by {days_late} day(s).",
                        "entity_type": "project",
                        "entity_id": project.id,
                        "entity_name": project.name,
                        "action_url": f"/projects/{project.id}",
                    }
                )
            if project.deadline and 0 <= (project.deadline - now).days <= 3 and float(project.progress or 0) < 80:
                risk_flags.append(
                    {
                        "type": "critical_deadline",
                        "severity": "high",
                        "message": f"{project.name} has a deadline within 3 days and is below 80% progress.",
                        "entity_type": "project",
                        "entity_id": project.id,
                        "entity_name": project.name,
                        "action_url": f"/projects/{project.id}",
                    }
                )

        for employee in employees:
            if (employee.current_load or 0) > 0.9 * (employee.max_capacity or 1):
                risk_flags.append(
                    {
                        "type": "overloaded_team",
                        "severity": "high",
                        "message": f"{employee.user.full_name if employee.user else 'Employee'} is overloaded.",
                        "entity_type": "employee",
                        "entity_id": employee.id,
                        "entity_name": employee.user.full_name if employee.user else f"Employee {employee.id}",
                        "action_url": "/employees",
                    }
                )

        for client in clients:
            for project in projects_by_client.get(client.id, []):
                if (
                    project.payment_status == "pending"
                    and project.completed_at
                    and project.completed_at < now - timedelta(days=30)
                ):
                    risk_flags.append(
                        {
                            "type": "overdue_payment",
                            "severity": "high" if (now - project.completed_at).days < 60 else "critical",
                            "message": f"{client.company_name} has an overdue payment for {project.name}.",
                            "entity_type": "client",
                            "entity_id": client.id,
                            "entity_name": client.company_name,
                            "action_url": f"/projects/{project.id}",
                        }
                    )

        for project in projects:
            for blocker in blockers_by_project.get(project.id, []):
                if blocker.severity == "critical" and blocker.status == "open":
                    risk_flags.append(
                        {
                            "type": "unresolved_blocker",
                            "severity": "critical",
                            "message": f"Critical blocker open on {project.name}: {blocker.description}",
                            "entity_type": "project",
                            "entity_id": project.id,
                            "entity_name": project.name,
                            "action_url": f"/projects/{project.id}",
                        }
                    )

        return risk_flags
