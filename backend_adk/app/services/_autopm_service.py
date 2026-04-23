# app/services/_autopm_service.py
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import random

from sqlalchemy.orm import Session

from app.models._project import Project
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._employee_profile import EmployeeProfile
from app.models._checkpoint import Checkpoint
from app.models._communication import Communication
from app.models._performance_point import PerformancePoint
from app.models._audit_log import AuditLog
from app.models._blocker import Blocker
from app.services._assignment_engine import AssignmentEngine
from app.services._llm_service import LLMService


class AutoPMService:
    def __init__(self, db: Session):
        self.db = db
        self.assignment_engine = AssignmentEngine(db)
        self.llm_service = LLMService()

    def intake_project(
        self,
        request_text: str,
        admin_user_id: int,
        budget: float = 0.0,
        priority: str = "medium",
        deadline: Optional[datetime] = None,
        tenant_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        parsed = self.llm_service.parse_project_intake(request_text)

        project = Project(
            name=parsed.get("project_title", "Autonomous Project"),
            description=parsed.get("project_summary", request_text),
            admin_id=admin_user_id,
            tenant_id=tenant_id,          # was always NULL before (C4)
            budget=budget,
            priority=priority,
            deadline=deadline,
            status="planning",
            custom_fields={"project_complexity": parsed.get("project_complexity", 0.6)},
        )
        self.db.add(project)
        self.db.flush()

        created_task_ids = []
        for t in parsed.get("tasks", []):
            task = Task(
                project_id=project.id,
                description=t.get("title", "Task"),
                difficulty=t.get("difficulty", "medium"),
                urgency=t.get("urgency", "medium"),
                estimated_time=float(t.get("estimated_time", 8)),
                required_skills=t.get("required_skills", {}),
                status="pending",
            )
            self.db.add(task)
            self.db.flush()
            created_task_ids.append(task.id)

            self._log(
                action="task_created_from_intake",
                entity_type="task",
                entity_id=task.id,
                reason=f"Created from intake for project {project.id}",
                context={"description": task.description},
            )

        self._log(
            action="project_intake",
            entity_type="project",
            entity_id=project.id,
            reason="Project intake parsed and tasks generated",
            context={"task_count": len(created_task_ids)},
        )

        self.db.commit()
        return {
            "project_id": project.id,
            "project_name": project.name,
            "task_ids": created_task_ids,
            "task_count": len(created_task_ids),
            "llm_enabled": self.llm_service.enabled,
        }

    def assign_project_tasks(self, project_id: int) -> Dict[str, Any]:
        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        assigned, skipped = [], []

        for task in tasks:
            # Skip if active assignment exists.
            active = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status.in_(["pending", "accepted", "in-progress"]),
            ).first()
            if active:
                skipped.append(task.id)
                continue

            assignment, confidence, reasoning = self.assignment_engine.assign_task(task, override=True)
            if not assignment:
                skipped.append(task.id)
                self._log(
                    action="assignment_failed",
                    entity_type="task",
                    entity_id=task.id,
                    reason=reasoning,
                    context={},
                )
                continue

            assignment.status = "pending"
            task.status = "pending"
            self.db.merge(assignment)
            self.db.merge(task)

            self._communication(
                type_="ticket",
                from_actor="agent",
                to_actor=f"employee:{assignment.employee_id}",
                subject=f"Task Assignment Offer #{task.id}",
                body=f"You have been assigned task '{task.description}'. Please accept, deny, or negotiate.",
                project_id=project_id,
                task_id=task.id,
            )
            self._log(
                action="task_assigned",
                entity_type="task",
                entity_id=task.id,
                reason=reasoning,
                context={"employee_id": assignment.employee_id, "confidence": confidence},
            )
            assigned.append(
                {
                    "task_id": task.id,
                    "employee_id": assignment.employee_id,
                    "confidence": round(confidence, 2),
                }
            )

        self.db.commit()
        return {"project_id": project_id, "assigned": assigned, "skipped_task_ids": skipped}

    def handle_assignment_response(
        self,
        assignment_id: int,
        response: str,
        negotiation_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        assignment = self.db.query(TaskAssignment).filter(TaskAssignment.id == assignment_id).first()
        if not assignment:
            raise ValueError("Assignment not found")

        task = self.db.query(Task).filter(Task.id == assignment.task_id).first()
        if not task:
            raise ValueError("Task not found")

        response = response.lower().strip()
        if response not in ["accepted", "denied", "negotiating"]:
            raise ValueError("Response must be accepted, denied, or negotiating")

        if response == "accepted":
            assignment.status = "accepted"
            assignment.started_at = datetime.utcnow()
            task.status = "running"
            self._create_default_checkpoints(task.id)
            self._log("assignment_accepted", "assignment", assignment.id, "Employee accepted assignment", {})

        elif response == "negotiating":
            assignment.status = "negotiating"
            assignment.notes = negotiation_notes
            if task.deadline:
                task.deadline = task.deadline + timedelta(days=1)
            self._log(
                "assignment_negotiating",
                "assignment",
                assignment.id,
                "Employee requested negotiation",
                {"notes": negotiation_notes},
            )

        else:
            assignment.status = "denied"
            assignment.notes = negotiation_notes
            self._log(
                "assignment_denied",
                "assignment",
                assignment.id,
                "Employee denied assignment",
                {"notes": negotiation_notes},
            )
            reassignment = self._reassign_after_denial(task.id, denied_employee_id=assignment.employee_id)
            self.db.commit()
            return {
                "assignment_id": assignment.id,
                "response": response,
                "task_id": task.id,
                "reassignment": reassignment,
            }

        self.db.merge(assignment)
        self.db.merge(task)
        self.db.commit()
        return {"assignment_id": assignment.id, "response": response, "task_id": task.id}

    def run_project_simulation(self, project_id: int, seed: Optional[int] = None) -> Dict[str, Any]:
        if seed is not None:
            random.seed(seed)

        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        logs = []

        for task in tasks:
            assignment = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status.in_(["accepted", "in-progress", "pending"]),
            ).order_by(TaskAssignment.assigned_at.desc()).first()

            if not assignment:
                continue

            # Resolve pending offers for demo speed.
            if assignment.status == "pending":
                assignment.status = "accepted"
                assignment.started_at = datetime.utcnow()

            # Stochastic simulation of execution outcomes.
            roll = random.random()
            if roll < 0.15:
                task.status = "blocked"
                blocker = Blocker(
                    task_id=task.id,
                    blocker_type="execution",
                    severity="high",
                    description="Automated simulation detected a delivery blocker",
                    status="open",
                )
                self.db.add(blocker)
                suggestion = self.llm_service.suggest_blocker_resolution(
                    {"task_id": task.id, "task": task.description, "project_id": project_id}
                )
                self._communication(
                    type_="ticket",
                    from_actor="agent",
                    to_actor="admin",
                    subject=f"Blocker detected on task {task.id}",
                    body=suggestion,
                    project_id=project_id,
                    task_id=task.id,
                )
                logs.append({"task_id": task.id, "status": "blocked"})

            elif roll < 0.75:
                task.status = "running"
                assignment.status = "in-progress"
                self._progress_checkpoints(task.id)
                logs.append({"task_id": task.id, "status": "running"})

            else:
                task.status = "done"
                assignment.status = "completed"
                assignment.completed_at = datetime.utcnow()
                assignment.actual_hours = max(1.0, (task.estimated_time or 8) * random.uniform(0.85, 1.25))
                self._complete_all_checkpoints(task.id)
                logs.append({"task_id": task.id, "status": "done"})

            self.db.merge(task)
            self.db.merge(assignment)
            self._log(
                action="simulation_tick",
                entity_type="task",
                entity_id=task.id,
                reason=f"Task moved to {task.status}",
                context={"project_id": project_id},
            )

        self.db.commit()
        return {"project_id": project_id, "events": logs}

    def generate_daily_digest(self) -> Dict[str, Any]:
        active_projects = self.db.query(Project).filter(Project.status.in_(["planning", "in-progress"])).all()
        due_today = self.db.query(Task).filter(Task.status.in_(["pending", "running", "blocked"])).all()
        open_blockers = self.db.query(Blocker).filter(Blocker.status == "open").all()
        pending_assignments = self.db.query(TaskAssignment).filter(TaskAssignment.status == "pending").all()

        yesterday = datetime.utcnow() - timedelta(days=1)
        points_yesterday = self.db.query(PerformancePoint).filter(PerformancePoint.awarded_at >= yesterday).all()

        return {
            "active_projects": [
                {"id": p.id, "name": p.name, "status": p.status, "health_score": self._project_health_score(p.id)}
                for p in active_projects
            ],
            "tasks_due_or_active_today": len(due_today),
            "open_blockers": len(open_blockers),
            "pending_assignments": len(pending_assignments),
            "performance_points_awarded_yesterday": sum(pp.points for pp in points_yesterday),
        }

    def generate_client_update(self, project_id: int) -> Dict[str, Any]:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")

        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        completed = len([t for t in tasks if t.status == "done"])
        in_progress = len([t for t in tasks if t.status in ["running", "pending"]])
        blocked = len([t for t in tasks if t.status == "blocked"])

        context = {
            "project_id": project.id,
            "project_name": project.name,
            "project_status": project.status,
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "blocked_tasks": blocked,
            "health_score": self._project_health_score(project_id),
        }
        message = self.llm_service.generate_client_update(context)

        self._communication(
            type_="email",
            from_actor="agent",
            to_actor=f"client:{project.client_id}" if project.client_id else "client:unknown",
            subject=f"Progress Update: {project.name}",
            body=message,
            project_id=project_id,
            task_id=None,
        )
        self.db.commit()
        return {"project_id": project_id, "message": message}

    def close_project(self, project_id: int) -> Dict[str, Any]:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")

        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        if any(t.status != "done" for t in tasks):
            raise ValueError("Cannot close project: all tasks are not done yet")

        awarded = self._award_performance_points(project_id, tasks)
        project.status = "completed"
        project.completed_at = datetime.utcnow()
        project.progress = 100

        self._log(
            action="project_closed",
            entity_type="project",
            entity_id=project_id,
            reason="All tasks done and closure initiated",
            context={"points_awarded_count": len(awarded)},
        )
        self.db.merge(project)
        self.db.commit()
        return {"project_id": project_id, "status": project.status, "awards": awarded}

    def _create_default_checkpoints(self, task_id: int) -> None:
        now = datetime.utcnow()
        checkpoints = [
            Checkpoint(task_id=task_id, title="Kickoff & Plan", due_date=now + timedelta(days=1)),
            Checkpoint(task_id=task_id, title="Mid Execution", due_date=now + timedelta(days=3)),
            Checkpoint(task_id=task_id, title="Final Delivery", due_date=now + timedelta(days=5)),
        ]
        for cp in checkpoints:
            self.db.add(cp)

    def _progress_checkpoints(self, task_id: int) -> None:
        cp = self.db.query(Checkpoint).filter(
            Checkpoint.task_id == task_id,
            Checkpoint.status == "pending",
        ).order_by(Checkpoint.created_at.asc()).first()
        if cp:
            cp.status = "completed"
            cp.completed_at = datetime.utcnow()
            self.db.merge(cp)

    def _complete_all_checkpoints(self, task_id: int) -> None:
        checkpoints = self.db.query(Checkpoint).filter(Checkpoint.task_id == task_id).all()
        for cp in checkpoints:
            if cp.status != "completed":
                cp.status = "completed"
                cp.completed_at = datetime.utcnow()
                self.db.merge(cp)

    def _reassign_after_denial(self, task_id: int, denied_employee_id: int) -> Dict[str, Any]:
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"reassigned": False, "reason": "Task not found"}

        employees = self.db.query(EmployeeProfile).filter(
            EmployeeProfile.availability_status == "available",
            EmployeeProfile.id != denied_employee_id,
            EmployeeProfile.current_load < EmployeeProfile.max_capacity,
        ).all()

        if not employees:
            self._log(
                action="reassignment_failed",
                entity_type="task",
                entity_id=task_id,
                reason="No employees available after denial",
                context={},
            )
            return {"reassigned": False, "reason": "No alternative employee available"}

        scored = [(emp, self.assignment_engine._calculate_employee_score(emp, task)) for emp in employees]
        scored.sort(key=lambda x: x[1], reverse=True)
        best_emp, score = scored[0]

        new_assignment = TaskAssignment(
            task_id=task_id,
            employee_id=best_emp.id,
            status="pending",
            assignment_confidence=score,
            estimated_hours=task.estimated_time,
        )
        self.db.add(new_assignment)

        self._communication(
            type_="ticket",
            from_actor="agent",
            to_actor=f"employee:{best_emp.id}",
            subject=f"Reassignment Offer for Task #{task_id}",
            body=f"Task '{task.description}' has been reassigned to you after prior denial.",
            project_id=task.project_id,
            task_id=task_id,
        )
        self._log(
            action="task_reassigned",
            entity_type="task",
            entity_id=task_id,
            reason="Reassigned after denial",
            context={"employee_id": best_emp.id, "confidence": score},
        )
        return {"reassigned": True, "employee_id": best_emp.id, "confidence": round(score, 2)}

    def _award_performance_points(self, project_id: int, tasks: List[Task]) -> List[Dict[str, Any]]:
        awarded = []
        for task in tasks:
            assignment = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status == "completed",
            ).order_by(TaskAssignment.completed_at.desc()).first()
            if not assignment:
                continue

            complexity_weight = {"easy": 0.5, "medium": 0.75, "hard": 1.0}.get(task.difficulty, 0.75)
            on_time = 1.0
            if task.deadline and assignment.completed_at and assignment.completed_at > task.deadline:
                on_time = 0.6

            blocker_penalty = 0.9 if task.status == "blocked" else 1.0
            points = round(100 * (0.4 * complexity_weight + 0.3 * on_time + 0.2 * blocker_penalty + 0.1 * 1.0), 2)

            pp = PerformancePoint(
                employee_id=assignment.employee_id,
                project_id=project_id,
                task_id=task.id,
                points=points,
                reason="Automated closure scoring",
            )
            self.db.add(pp)
            awarded.append({"employee_id": assignment.employee_id, "task_id": task.id, "points": points})

        return awarded

    def _project_health_score(self, project_id: int) -> float:
        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        if not tasks:
            return 100.0

        total = len(tasks)
        done = len([t for t in tasks if t.status == "done"])
        blocked = len([t for t in tasks if t.status == "blocked"])
        running = len([t for t in tasks if t.status == "running"])
        health = 100 * ((done / total) * 0.6 + (running / total) * 0.3 + ((total - blocked) / total) * 0.1)
        return round(max(0.0, min(100.0, health)), 2)

    def _communication(
        self,
        type_: str,
        from_actor: str,
        to_actor: str,
        subject: str,
        body: str,
        project_id: Optional[int],
        task_id: Optional[int],
    ) -> None:
        comm = Communication(
            type=type_,
            from_actor=from_actor,
            to_actor=to_actor,
            subject=subject,
            body=body,
            project_id=project_id,
            task_id=task_id,
            status="sent",
        )
        self.db.add(comm)

    def _log(self, action: str, entity_type: str, entity_id: int, reason: str, context: Dict[str, Any]) -> None:
        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            decision_reason=reason,
            performed_by="agent",
            context_data=context,
        )
        self.db.add(log)
