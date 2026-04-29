from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models._employee_profile import EmployeeProfile
from app.models._employee_metrics import EmployeeMetrics

XP_PER_LEVEL = 1000

# Base XP by task priority
TASK_BASE_XP = {
    "low": 10,
    "medium": 20,
    "high": 35,
    "critical": 50,
}


def _awarded_xp(base: int, level: int) -> int:
    """XP earned decreases exponentially per level."""
    earned = base / (level ** 1.5)
    return max(1, round(earned))


def calculate_reliability(
    level: int,
    xp: int,
    joining_date: Optional[date],
    initial_reliability: float = 0.5,
) -> float:
    """
    Reliability drifts up slowly based on level+XP and in-company tenure.
    Early levels have minimal impact; real gains start at Level 3+.
    """
    # In-company years from joining_date (capped contribution at 15 years)
    years = 0.0
    if joining_date:
        years = (datetime.utcnow().date() - joining_date).days / 365.25

    # Level contribution ceiling per level (grows non-linearly)
    # L1=0, L2=0.06, L3=0.16, L4=0.28, L5=0.42 (capped at 0.45)
    level_ceiling = min(0.45, max(0.0, (level - 1) ** 1.3 * 0.07))

    # Scale by fraction of current level completed
    xp_fraction = min(1.0, xp / XP_PER_LEVEL)
    level_contribution = level_ceiling * xp_fraction

    # Tenure contribution — slow, honest, caps at 0.15 after ~10 years
    tenure_contribution = min(0.15, years * 0.015)

    total_delta = level_contribution + tenure_contribution
    return round(min(1.0, max(0.0, initial_reliability + total_delta)), 3)


def award_xp(db: Session, employee_profile_id: int, priority: str = "medium") -> EmployeeProfile:
    """Award XP for a completed task and recalculate reliability."""
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == employee_profile_id).first()
    if not profile:
        return None

    base = TASK_BASE_XP.get(priority, 20)
    earned = _awarded_xp(base, profile.level)

    profile.xp = (profile.xp or 0) + earned
    # Level up if XP hits ceiling
    while profile.xp >= XP_PER_LEVEL:
        profile.xp -= XP_PER_LEVEL
        profile.level = (profile.level or 1) + 1

    # Recalculate reliability
    metrics = profile.metrics
    if not metrics:
        metrics = EmployeeMetrics(employee_id=profile.id)
        db.add(metrics)
        db.flush()

    initial = metrics.reliability_score or 0.5
    metrics.reliability_score = calculate_reliability(
        level=profile.level,
        xp=profile.xp,
        joining_date=profile.joining_date,
        initial_reliability=initial,
    )
    metrics.updated_at = datetime.utcnow()

    db.add(profile)
    db.add(metrics)
    return profile
