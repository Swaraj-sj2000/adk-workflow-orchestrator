# app/agents/_planning_agent.py

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent


class PlanningAgent(BaseAgent):
    agent_name = "planning_agent"
    role = "work_breakdown"
    stage = "planning"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        parsed = shared_context["parsed_brief"]
        deadline = shared_context.get("deadline")
        raw_tasks = parsed.get("tasks", [])

        tasks: List[Dict[str, Any]] = []
        dependencies: List[Dict[str, Any]] = []

        for index, raw_task in enumerate(raw_tasks):
            due_date = None
            if deadline and raw_tasks:
                now = datetime.now(timezone.utc)
                dl = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
                days_remaining = max(1, (dl - now).days)
                slot = max(1, days_remaining // len(raw_tasks))
                due_date = (now + timedelta(days=slot * (index + 1))).isoformat()

            task_blueprint = {
                "sequence": index + 1,
                "title": raw_task.get("title") or raw_task.get("description") or f"Task {index + 1}",
                "description": raw_task.get("description") or raw_task.get("title") or "Planned task",
                "difficulty": raw_task.get("difficulty", "medium"),
                "urgency": raw_task.get("urgency", "medium"),
                "estimated_time": float(raw_task.get("estimated_time", 8)),
                "required_skills": raw_task.get("required_skills", {}),
                "suggested_due_date": due_date,
            }
            tasks.append(task_blueprint)

            if index > 0:
                dependencies.append(
                    {
                        "task_sequence": index + 1,
                        "depends_on_sequence": index,
                        "dependency_type": "blocking",
                    }
                )

        output_payload = {
            "project_title": parsed.get("project_title", "Untitled Project"),
            "project_summary": parsed.get("project_summary", shared_context["request_text"]),
            "project_complexity": parsed.get("project_complexity", 0.7),
            "tasks": tasks,
            "dependencies": dependencies,
            "parallelizable_stages": [
                {
                    "after_stage": "planning",
                    "parallel_agents": ["staffing_agent", "risk_agent"],
                }
            ],
        }

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.78 if tasks else 0.35,
            reasoning="Converted intake brief into a structured execution plan with task ordering and basic dependencies",
            output_payload=output_payload,
            requires_human_review=not tasks,
        )
