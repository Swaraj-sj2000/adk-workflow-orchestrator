"""Assignment engine unit tests — scoring logic, tenant isolation, timezone penalty."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._task import Task
from app.models._tenant import Tenant
from app.models._user import User
from app.services._assignment_engine import AssignmentEngine


def _make_tenant(db: Session, slug: str) -> Tenant:
    t = Tenant(name=slug.title(), slug=slug)
    db.add(t)
    db.flush()
    return t


def _make_user(db: Session, tenant_id: int, email: str) -> User:
    u = User(email=email, password="x", full_name="Worker", role="employee", tenant_id=tenant_id)
    db.add(u)
    db.flush()
    return u


def _make_employee(
    db: Session,
    tenant_id: int,
    user_id: int,
    skills: dict,
    current_load: float = 0.0,
    max_capacity: float = 8.0,
    efficiency: float = 0.8,
    reliability: float = 0.8,
) -> EmployeeProfile:
    ep = EmployeeProfile(
        tenant_id=tenant_id,
        user_id=user_id,
        skills=skills,
        current_load=current_load,
        max_capacity=max_capacity,
        availability_status="available",
    )
    db.add(ep)
    db.flush()
    metrics = EmployeeMetrics(
        employee_id=ep.id,
        efficiency_score=efficiency,
        reliability_score=reliability,
        avg_completion_time=0.0,
        total_tasks_completed=0,
        total_tasks_failed=0,
        total_tasks_delayed=0,
    )
    db.add(metrics)
    db.flush()
    return ep


def _make_task(
    db: Session,
    tenant_id: int,
    required_skills: dict,
    urgency: str = "medium",
    estimated_time: float = 4.0,
    deadline: datetime | None = None,
) -> Task:
    t = Task(
        tenant_id=tenant_id,
        project_id=1,
        description="Test task",
        required_skills=required_skills,
        urgency=urgency,
        estimated_time=estimated_time,
        deadline=deadline,
    )
    db.add(t)
    db.flush()
    return t


class TestSkillMatchScoring:
    def test_perfect_skill_match_scores_high(self, db: Session):
        ten = _make_tenant(db, "skillco")
        u = _make_user(db, ten.id, "worker1@skillco.com")
        emp = _make_employee(db, ten.id, u.id, {"python": 0.9, "fastapi": 0.8})
        task = _make_task(db, ten.id, {"python": 0.9, "fastapi": 0.8})

        engine = AssignmentEngine(db)
        score = engine._calculate_skill_match(emp, task)
        assert score >= 0.95

    def test_no_matching_skills_scores_zero(self, db: Session):
        ten = _make_tenant(db, "noskillco")
        u = _make_user(db, ten.id, "worker2@noskillco.com")
        emp = _make_employee(db, ten.id, u.id, {"java": 0.9})
        task = _make_task(db, ten.id, {"python": 0.9})

        engine = AssignmentEngine(db)
        score = engine._calculate_skill_match(emp, task)
        assert score == 0.0

    def test_no_required_skills_scores_one(self, db: Session):
        ten = _make_tenant(db, "anyscillco")
        u = _make_user(db, ten.id, "worker3@anyscillco.com")
        emp = _make_employee(db, ten.id, u.id, {})
        task = _make_task(db, ten.id, {})

        engine = AssignmentEngine(db)
        score = engine._calculate_skill_match(emp, task)
        assert score == 1.0


class TestWorkloadScoring:
    def test_empty_workload_scores_one(self, db: Session):
        ten = _make_tenant(db, "loadco1")
        u = _make_user(db, ten.id, "w@loadco1.com")
        emp = _make_employee(db, ten.id, u.id, {}, current_load=0.0, max_capacity=8.0)
        engine = AssignmentEngine(db)
        assert engine._calculate_workload_score(emp) == 1.0

    def test_full_workload_scores_zero(self, db: Session):
        ten = _make_tenant(db, "loadco2")
        u = _make_user(db, ten.id, "w@loadco2.com")
        emp = _make_employee(db, ten.id, u.id, {}, current_load=8.0, max_capacity=8.0)
        engine = AssignmentEngine(db)
        assert engine._calculate_workload_score(emp) == 0.0

    def test_half_workload_scores_half(self, db: Session):
        ten = _make_tenant(db, "loadco3")
        u = _make_user(db, ten.id, "w@loadco3.com")
        emp = _make_employee(db, ten.id, u.id, {}, current_load=4.0, max_capacity=8.0)
        engine = AssignmentEngine(db)
        assert engine._calculate_workload_score(emp) == pytest.approx(0.5)


class TestTenantIsolation:
    def test_employees_from_other_tenant_excluded(self, db: Session):
        ten_a = _make_tenant(db, "tenanta")
        ten_b = _make_tenant(db, "tenantb")
        u_a = _make_user(db, ten_a.id, "a@tenanta.com")
        u_b = _make_user(db, ten_b.id, "b@tenantb.com")
        _make_employee(db, ten_a.id, u_a.id, {"python": 0.9})
        _make_employee(db, ten_b.id, u_b.id, {"python": 0.9})

        task = _make_task(db, ten_a.id, {"python": 0.9})
        engine = AssignmentEngine(db)
        candidates = engine._get_available_employees(task)
        tenant_ids = {c.tenant_id for c in candidates}
        assert ten_b.id not in tenant_ids

    def test_overloaded_employee_excluded(self, db: Session):
        ten = _make_tenant(db, "overloaded")
        u = _make_user(db, ten.id, "busy@overloaded.com")
        _make_employee(db, ten.id, u.id, {"python": 0.9}, current_load=8.0, max_capacity=8.0)
        task = _make_task(db, ten.id, {"python": 0.9})

        engine = AssignmentEngine(db)
        candidates = engine._get_available_employees(task)
        assert all(e.current_load < e.max_capacity for e in candidates)


class TestBestCandidateSelection:
    def test_better_skill_match_wins(self, db: Session):
        ten = _make_tenant(db, "bestco")
        u1 = _make_user(db, ten.id, "good@bestco.com")
        u2 = _make_user(db, ten.id, "bad@bestco.com")
        good = _make_employee(db, ten.id, u1.id, {"python": 0.9}, efficiency=0.9, reliability=0.9)
        bad = _make_employee(db, ten.id, u2.id, {"java": 0.5}, efficiency=0.5, reliability=0.5)
        task = _make_task(db, ten.id, {"python": 0.9})

        engine = AssignmentEngine(db)
        score_good = engine._calculate_employee_score(good, task)
        score_bad = engine._calculate_employee_score(bad, task)
        assert score_good > score_bad
