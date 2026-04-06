# app/utils/_helpers.py
from sqlalchemy.orm import Session
from app.models._employee_profile import EmployeeProfile
from app.models._employee_metrics import EmployeeMetrics
from app.models._task_assignment import TaskAssignment
from app.models._task_progress import TaskProgress
from typing import List, Tuple, Optional
from datetime import datetime


class EmployeeHelper:
    """Helper functions for employee operations."""
    
    @staticmethod
    def update_metrics_on_task_completion(
        db: Session,
        employee_id: int,
        estimated_hours: float,
        actual_hours: float,
        completed_successfully: bool
    ) -> EmployeeMetrics:
        """
        Update employee metrics after task completion.
        Recalculates efficiency and reliability scores.
        """
        metrics = db.query(EmployeeMetrics).filter(
            EmployeeMetrics.employee_id == employee_id
        ).first()
        
        if not metrics:
            return None
        
        # Update completion count
        metrics.total_tasks_completed += 1
        
        if not completed_successfully:
            metrics.total_tasks_failed += 1
        
        # Update average completion time
        total_hours = (metrics.avg_completion_time or 0) * (metrics.total_tasks_completed - 1)
        total_hours += actual_hours
        metrics.avg_completion_time = total_hours / metrics.total_tasks_completed
        
        # Update efficiency score (actual vs estimated)
        if estimated_hours > 0:
            efficiency_ratio = min(actual_hours / estimated_hours, 1.0)
            metrics.efficiency_score = (metrics.efficiency_score * 0.7) + (efficiency_ratio * 0.3)
        
        # Update reliability score
        if metrics.total_tasks_completed > 0:
            success_rate = (metrics.total_tasks_completed - metrics.total_tasks_failed) / metrics.total_tasks_completed
            metrics.reliability_score = success_rate
        
        metrics.updated_at = datetime.utcnow()
        db.merge(metrics)
        db.commit()
        
        return metrics
    
    @staticmethod
    def get_employee_workload_status(
        db: Session,
        employee_id: int
    ) -> dict:
        """Get current workload status for an employee."""
        profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.id == employee_id
        ).first()
        
        if not profile:
            return None
        
        utilization = profile.current_load / profile.max_capacity if profile.max_capacity > 0 else 0
        
        return {
            "employee_id": employee_id,
            "current_load": profile.current_load,
            "max_capacity": profile.max_capacity,
            "utilization_percentage": round(utilization * 100, 2),
            "available_capacity": max(0, profile.max_capacity - profile.current_load),
            "status": "overloaded" if utilization > 1.0 else "full" if utilization >= 0.9 else "available"
        }


class TaskHelper:
    """Helper functions for task operations."""
    
    @staticmethod
    def get_task_progress_summary(
        db: Session,
        task_id: int
    ) -> dict:
        """Get comprehensive progress information for a task."""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        from app.models._task import Task
        
        progress = db.query(TaskProgress).filter(
            TaskProgress.task_id == task_id
        ).first()
        
        assignments = db.query(TaskAssignment).filter(
            TaskAssignment.task_id == task_id
        ).all()
        
        return {
            "task_id": task_id,
            "status": task.status,
            "completion_percentage": progress.completion_percentage if progress else 0,
            "total_assignments": len(assignments),
            "active_assignments": len([a for a in assignments if a.status == "in-progress"]),
            "estimated_time": task.estimated_time,
            "actual_hours_spent": progress.actual_hours_spent if progress else 0,
            "on_track": progress.is_on_track if progress else True,
            "deadline": task.deadline,
            "time_remaining": (task.deadline - datetime.utcnow()).total_seconds() / 3600 if task.deadline else None
        }
    
    @staticmethod
    def assign_to_multiple_employees(
        db: Session,
        task_id: int,
        employee_ids: List[int],
        estimated_hours_each: float
    ) -> List[TaskAssignment]:
        """Assign same task to multiple employees (for collaborative tasks)."""
        from app.models._task import Task
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return []
        
        assignments = []
        for emp_id in employee_ids:
            assignment = TaskAssignment(
                task_id=task_id,
                employee_id=emp_id,
                estimated_hours=estimated_hours_each,
                status="assigned"
            )
            db.add(assignment)
            assignments.append(assignment)
        
        db.commit()
        return assignments


class ProjectHelper:
    """Helper functions for project operations."""
    
    @staticmethod
    def calculate_project_progress(
        db: Session,
        project_id: int
    ) -> dict:
        """Calculate overall project progress and metrics."""
        from app.models._project import Project
        
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None
        
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        
        if not tasks:
            return {
                "project_id": project_id,
                "total_tasks": 0,
                "completion_percentage": 0,
                "completed_tasks": 0,
                "in_progress": 0,
                "blocked_tasks": 0
            }
        
        from app.models._task import Task
        
        completed = len([t for t in tasks if t.status == "done"])
        in_progress = len([t for t in tasks if t.status == "running"])
        blocked = len([t for t in tasks if t.status == "blocked"])
        
        progress = round((completed / len(tasks)) * 100, 2) if tasks else 0
        
        return {
            "project_id": project_id,
            "total_tasks": len(tasks),
            "completion_percentage": progress,
            "completed_tasks": completed,
            "in_progress": in_progress,
            "blocked_tasks": blocked,
            "pending_tasks": len([t for t in tasks if t.status == "pending"])
        }
