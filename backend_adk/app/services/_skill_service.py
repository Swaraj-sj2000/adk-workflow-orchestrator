# app/services/_skill_service.py
"""
Updates employee demonstrated_skills whenever they complete a task.

Demonstrated skills are stored as:
  {"python": {"score": 0.85, "tasks_done": 5, "last_updated": "2026-04-27"}}

The confidence score drifts toward the task's required level over time using
exponential moving average: new_score = 0.8 * old + 0.2 * task_level
This way one outlier task never fully resets a long track record.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models._employee_profile import EmployeeProfile
from app.models._task_assignment import TaskAssignment
from app.models._task import Task
from app.core._logging import get_logger

logger = get_logger(__name__)

_EMA_WEIGHT = 0.2  # weight given to each new completed task
_DIFFICULTY_BOOST = {"easy": 0.0, "medium": 0.05, "hard": 0.10}


def update_skill_confidence(db: Session, task: Task) -> None:
    """
    For every employee assigned to `task`, update their demonstrated_skills
    based on the task's required_skills and difficulty.
    Called by _task_service after a task transitions to 'done'.
    """
    required_skills: dict = task.required_skills or {}
    if not required_skills:
        return

    difficulty_boost = _DIFFICULTY_BOOST.get(task.difficulty or "medium", 0.05)

    assignments = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.task_id == task.id)
        .all()
    )

    for assignment in assignments:
        employee: EmployeeProfile | None = (
            db.query(EmployeeProfile)
            .filter(EmployeeProfile.id == assignment.employee_id)
            .first()
        )
        if not employee:
            continue

        # demonstrated_skills is stored as TEXT in the DB (JSON column may not
        # exist on older rows); normalise to dict.
        raw = employee.demonstrated_skills
        if isinstance(raw, str):
            try:
                demonstrated: dict = json.loads(raw)
            except Exception:
                demonstrated = {}
        else:
            demonstrated = dict(raw) if raw else {}

        today = datetime.now(timezone.utc).date().isoformat()

        for skill, required_level in required_skills.items():
            skill = skill.lower()
            target = float(required_level) + difficulty_boost
            target = min(target, 1.0)

            if skill in demonstrated:
                old_score = demonstrated[skill]["score"]
                new_score = round((1 - _EMA_WEIGHT) * old_score + _EMA_WEIGHT * target, 3)
                demonstrated[skill] = {
                    "score": new_score,
                    "tasks_done": demonstrated[skill].get("tasks_done", 0) + 1,
                    "last_updated": today,
                }
            else:
                demonstrated[skill] = {
                    "score": round(target, 3),
                    "tasks_done": 1,
                    "last_updated": today,
                }

        employee.demonstrated_skills = demonstrated
        db.add(employee)
        logger.debug(
            f"Skill growth: employee={employee.id}, "
            f"skills updated={list(required_skills.keys())}"
        )
