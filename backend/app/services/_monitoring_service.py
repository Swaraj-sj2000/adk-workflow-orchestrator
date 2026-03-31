# app/services/_monitoring_service.py
from sqlalchemy.orm import Session
from app.models._task import Task
from app.models._task_progress import TaskProgress
from app.models._employee_profile import EmployeeProfile
from app.models._blocker import Blocker
from app.models._task_assignment import TaskAssignment
from app.models._task_dependency import TaskDependency
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


class MonitoringService:
    """
    Monitors project and task health, detects risks, and triggers alerts.
    Detects:
    - overload situations
    - delay risks
    - blocked dependencies
    """
    
    OVERLOAD_THRESHOLD = 0.9  # 90% of capacity
    DELAY_RISK_THRESHOLD = 0.5  # If only 50% complete with 50% time left
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_project_health(self, project_id: int) -> Dict:
        """
        Get comprehensive health status of a project.
        """
        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        
        health_status = {
            "project_id": project_id,
            "total_tasks": len(tasks),
            "overload_alerts": [],
            "delay_alerts": [],
            "blocked_tasks": [],
            "dependency_issues": [],
            "risk_level": "low",  # low / medium / high / critical
            "timestamp": datetime.utcnow()
        }
        
        # Check each task
        for task in tasks:
            if task.status in ["completed", "cancelled"]:
                continue
            
            # Check for delays
            delay_alert = self._check_task_delay(task)
            if delay_alert:
                health_status["delay_alerts"].append(delay_alert)
            
            # Check for blocked dependencies
            blocked_deps = self._check_blocked_dependencies(task)
            if blocked_deps:
                health_status["blocked_tasks"].append({
                    "task_id": task.id,
                    "blocked_by": blocked_deps
                })
        
        # Check for employee overload
        employees = self.db.query(EmployeeProfile).filter(
            EmployeeProfile.id.in_([
                a.employee_id for a in self.db.query(TaskAssignment).all()
            ])
        ).all()
        
        for emp in employees:
            if emp.current_load / emp.max_capacity >= self.OVERLOAD_THRESHOLD:
                health_status["overload_alerts"].append({
                    "employee_id": emp.id,
                    "current_load": emp.current_load,
                    "capacity": emp.max_capacity,
                    "utilization": emp.current_load / emp.max_capacity
                })
        
        # Determine overall risk level
        health_status["risk_level"] = self._calculate_risk_level(health_status)
        
        return health_status
    
    def _check_task_delay(self, task: Task) -> Optional[Dict]:
        """
        Check if task is at risk of delay.
        Returns alert if task is not on track.
        """
        if not task.deadline:
            return None
        
        progress = self.db.query(TaskProgress).filter(
            TaskProgress.task_id == task.id
        ).first()
        
        if not progress:
            return None
        
        time_remaining = task.deadline - datetime.utcnow()
        completion_needed = 100 - progress.completion_percentage
        
        if time_remaining.total_seconds() < 0:
            # Deadline passed
            return {
                "task_id": task.id,
                "severity": "critical",
                "reason": "Deadline passed",
                "completion": progress.completion_percentage,
                "deadline": task.deadline
            }
        
        # Check if pace is sustainable
        hours_remaining = time_remaining.total_seconds() / 3600
        hours_needed = progress.estimated_hours_remaining or (task.estimated_time or 0)
        
        if hours_needed > hours_remaining and progress.completion_percentage < 70:
            return {
                "task_id": task.id,
                "severity": "high",
                "reason": "At risk of missing deadline",
                "completion": progress.completion_percentage,
                "hours_remaining": hours_remaining,
                "hours_needed": hours_needed,
                "deadline": task.deadline
            }
        
        return None
    
    def _check_blocked_dependencies(self, task: Task) -> List[int]:
        """
        Check if task is blocked by incomplete dependencies.
        """
        dependencies = self.db.query(TaskDependency).filter(
            TaskDependency.task_id == task.id
        ).all()
        
        blocked_by = []
        
        for dep in dependencies:
            if dep.dependency_type != "blocking":
                continue
            
            dependent_task = self.db.query(Task).filter(
                Task.id == dep.depends_on_task_id
            ).first()
            
            if dependent_task and dependent_task.status != "done":
                blocked_by.append(dep.depends_on_task_id)
        
        return blocked_by
    
    def _calculate_risk_level(self, health_status: Dict) -> str:
        """
        Calculate overall project risk level based on various factors.
        """
        risk_score = 0
        
        # Critical blockers
        if health_status["blocked_tasks"]:
            risk_score += len(health_status["blocked_tasks"]) * 2
        
        # Overload situations
        if health_status["overload_alerts"]:
            risk_score += len(health_status["overload_alerts"]) * 1.5
        
        # Delay risks
        critical_delays = [a for a in health_status["delay_alerts"] if a.get("severity") == "critical"]
        high_delays = [a for a in health_status["delay_alerts"] if a.get("severity") == "high"]
        risk_score += len(critical_delays) * 3 + len(high_delays) * 1
        
        # Determine level
        if risk_score >= 5:
            return "critical"
        elif risk_score >= 3:
            return "high"
        elif risk_score >= 1:
            return "medium"
        else:
            return "low"
    
    def get_risk_summary(self, project_id: int) -> Dict:
        """Get quick risk summary for dashboard."""
        health = self.check_project_health(project_id)
        
        return {
            "project_id": project_id,
            "risk_level": health["risk_level"],
            "critical_issues": (
                len([a for a in health["delay_alerts"] if a.get("severity") == "critical"]) +
                len(health["blocked_tasks"]) * 2
            ),
            "warning_count": len(health["overload_alerts"]),
            "needs_intervention": health["risk_level"] in ["high", "critical"]
        }
