# app/agents/_staffing_agent.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.models._employee_profile import EmployeeProfile


class StaffingAgent(BaseAgent):
    agent_name = "staffing_agent"
    role = "staffing"
    stage = "staffing"

    def __init__(self, db: Session, scoring_fn):
        self.db = db
        self.scoring_fn = scoring_fn

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        planned_tasks = shared_context["execution_plan"]["tasks"]
        employees = self.db.query(EmployeeProfile).filter(
            EmployeeProfile.availability_status == "available"
        ).all()

        recommendations: List[Dict[str, Any]] = []
        under_staffed = 0

        for task in planned_tasks:
            ranked = []
            for employee in employees:
                if employee.current_load >= employee.max_capacity:
                    continue

                task_like = type("TaskLike", (), {
                    "required_skills": task.get("required_skills", {}),
                    "estimated_time": task.get("estimated_time"),
                })()
                score = self.scoring_fn(employee, task_like)
                ranked.append(
                    {
                        "employee_profile_id": employee.id,
                        "user_id": employee.user_id,
                        "score": round(score, 3),
                        "current_load": employee.current_load,
                        "max_capacity": employee.max_capacity,
                        "skills": employee.skills or {},
                    }
                )

            ranked.sort(key=lambda item: item["score"], reverse=True)
            top = ranked[:3]
            if not top or top[0]["score"] < 0.5:
                under_staffed += 1

            recommendations.append(
                {
                    "task_sequence": task["sequence"],
                    "task_title": task["title"],
                    "recommended_candidates": top,
                    "recommended_owner": top[0] if top else None,
                }
            )

        confidence = 0.8 if recommendations and under_staffed == 0 else 0.55 if recommendations else 0.2
        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning="Ranked candidate owners for each task using current skills, availability, and capacity",
            output_payload={
                "staffing_recommendations": recommendations,
                "under_staffed_task_count": under_staffed,
                "available_employee_count": len(employees),
            },
            requires_human_review=under_staffed > 0 or not employees,
        )
