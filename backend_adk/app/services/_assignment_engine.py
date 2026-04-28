# app/services/_assignment_engine.py
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.models._task import Task
from app.models._employee_profile import EmployeeProfile
from app.models._task_assignment import TaskAssignment
from app.models._decision_log import DecisionLog
from app.models._user_preferences import UserPreferences
from app.schemas._task_assignment import TaskAssignmentCreate
from app.core._logging import get_logger
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import json

logger = get_logger(__name__)


class AssignmentEngine:
    """
    Core assignment engine for optimal task-to-employee matching.
    Uses weighted scoring based on skill match, workload, efficiency, and reliability.
    """

    # Weights for the scoring function
    WEIGHT_SKILL_MATCH = 0.35
    WEIGHT_LOW_WORKLOAD = 0.25
    WEIGHT_EFFICIENCY = 0.20
    WEIGHT_RELIABILITY = 0.20
    
    # Thresholds
    MIN_CONFIDENCE_SCORE = 0.5
    SKILL_MATCH_THRESHOLD = 0.6
    
    def __init__(self, db: Session):
        self.db = db

    def assign_task(
        self,
        task: Task,
        reason: str = "automatic_assignment",
        override: bool = False
    ) -> Tuple[Optional[TaskAssignment], float, str]:
        """
        Assign a task to the best-matching employee.
        
        Returns:
            (TaskAssignment, confidence_score, reasoning)
        """
        logger.info(f"Assigning task_id={task.id}, difficulty={task.difficulty}, urgency={task.urgency}")
        
        # Get available employees
        available_employees = self._get_available_employees(task)
        
        if not available_employees:
            logger.warning(f"No available employees for task_id={task.id}")
            return None, 0.0, "No available employees for this task"
        
        logger.debug(f"Found {len(available_employees)} available employees for task_id={task.id}")
        
        # Score all candidates
        scores_dict = {}
        for employee in available_employees:
            score = self._calculate_employee_score(employee, task)
            scores_dict[employee.id] = (score, employee)
        
        # Select best candidate
        best_employee_id = max(scores_dict, key=lambda x: scores_dict[x][0])
        best_score, best_employee = scores_dict[best_employee_id]
        
        confidence = best_score
        
        logger.info(
            f"Best match for task_id={task.id}: employee_id={best_employee_id}, "
            f"name={best_employee.title}, confidence={confidence:.2f}"
        )
        
        # Check if confidence is acceptable
        if confidence < self.MIN_CONFIDENCE_SCORE and not override:
            reasoning = f"Best match confidence ({confidence:.2f}) below threshold ({self.MIN_CONFIDENCE_SCORE})"
            logger.warning(f"Assignment rejected for task_id={task.id}: {reasoning}")
            return None, confidence, reasoning
        
        # Create assignment
        assignment = TaskAssignment(
            task_id=task.id,
            employee_id=best_employee.id,
            estimated_hours=task.estimated_time,
            assignment_confidence=confidence,
            status="assigned"
        )
        self.db.add(assignment)
        
        # Update employee workload atomically to avoid read-modify-write race
        # conditions when multiple concurrent requests assign tasks simultaneously.
        load_delta = task.estimated_time or 0
        self.db.execute(
            update(EmployeeProfile)
            .where(EmployeeProfile.id == best_employee.id)
            .values(current_load=EmployeeProfile.current_load + load_delta)
        )
        # Keep in-memory object consistent for logging below
        best_employee.current_load += load_delta
        
        logger.info(
            f"Task assignment created: task_id={task.id} -> employee_id={best_employee_id}, "
            f"estimated_hours={task.estimated_time}, new_load={best_employee.current_load}"
        )
        
        # Log the decision
        self._log_decision(
            decision_type="assignment",
            entity_type="task",
            entity_id=task.id,
            input_data={
                "available_employees": len(available_employees),
                "task_difficulty": task.difficulty,
                "task_urgency": task.urgency,
                "required_skills": task.required_skills,
            },
            decision_taken=f"Assigned to employee {best_employee.id}",
            confidence=confidence,
            reasoning=f"Best match with {', '.join(task.required_skills.keys())} skills"
        )
        
        self.db.commit()
        return assignment, confidence, f"Assigned to employee {best_employee.id} with confidence {confidence:.2f}"

    def suggest_reassignments(self, project_id: int) -> List[Dict]:
        """
        Suggest task reassignments based on current workload imbalance.
        """
        tasks = self.db.query(Task).filter(
            Task.project_id == project_id,
            Task.status.in_(["running", "pending"])
        ).all()
        
        suggestions = []
        
        for task in tasks:
            # Get current assignment
            current_assignment = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status == "in-progress"
            ).first()
            
            if not current_assignment:
                continue
            
            # Check if reassignment would help
            alternative_assignment, alt_confidence, alt_reasoning = self.assign_task(task, override=True)
            
            if alternative_assignment and alt_confidence > (current_assignment.assignment_confidence or 0) + 0.15:
                suggestions.append({
                    "task_id": task.id,
                    "current_employee_id": current_assignment.employee_id,
                    "suggested_employee_id": alternative_assignment.employee_id,
                    "confidence_improvement": alt_confidence - (current_assignment.assignment_confidence or 0),
                    "reason": alt_reasoning
                })
        
        return suggestions

    def _get_available_employees(self, task: Task) -> List[EmployeeProfile]:
        """Get employees available to take this task, scoped to the task's tenant."""
        query = self.db.query(EmployeeProfile).filter(
            EmployeeProfile.availability_status == "available",
            EmployeeProfile.current_load < EmployeeProfile.max_capacity * 1.5,
        )
        # Always restrict candidates to the same tenant as the task.
        # This prevents cross-tenant employee assignment (C3).
        if task.tenant_id is not None:
            query = query.filter(EmployeeProfile.tenant_id == task.tenant_id)

        return query.all()

    def _calculate_employee_score(self, employee: EmployeeProfile, task: Task) -> float:
        """
        Calculate match score for employee-task combination.
        score = w1*(skill_match) + w2*(low_workload) + w3*(efficiency) + w4*(reliability)
        """
        # 1. Skill match score
        skill_match_score = self._calculate_skill_match(employee, task)
        
        # 2. Workload score (lower workload = higher score)
        workload_score = self._calculate_workload_score(employee)
        
        # 3. Efficiency score (from metrics)
        efficiency_score = employee.metrics.efficiency_score if employee.metrics else 0.5
        
        # 4. Reliability score (from metrics)
        reliability_score = employee.metrics.reliability_score if employee.metrics else 0.5

        timezone_penalty = 0.0
        if task.deadline and task.deadline <= datetime.utcnow() + timedelta(hours=24):
            preferences = self.db.query(UserPreferences).filter(UserPreferences.user_id == employee.user_id).first()
            employee_timezone = preferences.timezone if preferences and preferences.timezone else "UTC"
            try:
                import pytz

                employee_hour = datetime.now(pytz.timezone(employee_timezone)).hour
                if employee_hour >= 22 or employee_hour < 7:
                    timezone_penalty = 0.15
            except Exception:
                timezone_penalty = 0.0
        
        # Weighted sum
        total_score = (
            self.WEIGHT_SKILL_MATCH * skill_match_score +
            self.WEIGHT_LOW_WORKLOAD * workload_score +
            self.WEIGHT_EFFICIENCY * efficiency_score +
            self.WEIGHT_RELIABILITY * reliability_score
        ) - timezone_penalty
        
        return total_score

    # Maps verbose / LLM-generated skill names → canonical profile skill keys
    _SKILL_ALIASES: Dict[str, str] = {
        "backend_development": "backend",
        "backend_engineering": "backend",
        "server_side": "backend",
        "frontend_development": "frontend",
        "frontend_engineering": "frontend",
        "ui_development": "frontend",
        "machine_learning": "llm",
        "deep_learning": "modeling",
        "neural_network": "modeling",
        "model_training": "modeling",
        "ai_model": "llm",
        "natural_language_processing": "llm",
        "nlp": "llm",
        "computer_vision": "modeling",
        "data_science": "data",
        "data_engineering": "data",
        "data_pipeline": "data",
        "data_visualization": "analytics",
        "database_design": "backend",
        "sql": "backend",
        "api_integration": "api",
        "api_development": "api",
        "rest_api": "api",
        "cloud_infrastructure": "cloud",
        "infrastructure": "devops",
        "ci_cd": "devops",
        "cicd": "devops",
        "notification_systems": "backend",
        "messaging": "backend",
        "search": "backend",
        "semantic_search": "llm",
        "prompt_engineering": "llm",
        "prompt_engineer": "llm",
        "project_management": "project-management",
        "design_systems": "design-systems",
        "ui_ux": "design-systems",
        "ux": "design-systems",
        "business_analysis": "project-management",
        "documentation": "communication",
        "testing": "qa",
        "automation_testing": "automation",
        "security_review": "security",
        "devops_engineering": "devops",
        "cloud_computing": "cloud",
        "reporting": "analytics",
        "client_success": "client-success",
        "client_management": "client-success",
        "delivery": "delivery",
        "delivery_management": "delivery",
    }

    def _normalise_skill(self, skill: str) -> str:
        """Lowercase + underscore → look up alias, else return as-is."""
        normalised = skill.lower().replace(" ", "_").replace("-", "_")
        return self._SKILL_ALIASES.get(normalised, normalised)

    def _calculate_skill_match(self, employee: EmployeeProfile, task: Task) -> float:
        """
        Calculate how well employee's skills match task requirements.
        Blends declared skills (70%) with demonstrated skills from completed
        tasks (30%) so proven performance influences assignment.
        """
        if not task.required_skills:
            return 1.0

        import json
        declared_skills: dict = employee.skills or {}
        raw_demo = employee.demonstrated_skills
        if isinstance(raw_demo, str):
            try:
                demonstrated_skills: dict = json.loads(raw_demo)
            except Exception:
                demonstrated_skills = {}
        else:
            demonstrated_skills = dict(raw_demo) if raw_demo else {}

        matched_skills = []
        for required_skill, required_level in task.required_skills.items():
            canonical = self._normalise_skill(required_skill)
            declared_level = declared_skills.get(required_skill) or declared_skills.get(canonical)
            demo_entry = demonstrated_skills.get(required_skill) or demonstrated_skills.get(canonical)
            demo_level = demo_entry["score"] if isinstance(demo_entry, dict) else demo_entry

            if declared_level is None and demo_level is None:
                continue

            # Blend: if both available, weight declared 70% / demonstrated 30%
            if declared_level is not None and demo_level is not None:
                blended = 0.7 * float(declared_level) + 0.3 * float(demo_level)
            elif demo_level is not None:
                blended = float(demo_level)
            else:
                blended = float(declared_level)

            skill_score = 1.0 - abs(blended - float(required_level))
            matched_skills.append(max(0.0, skill_score))

        if not matched_skills:
            return 0.0

        return sum(matched_skills) / len(matched_skills)

    def _calculate_workload_score(self, employee: EmployeeProfile) -> float:
        """
        Calculate workload score (0-1, higher = less workload).
        """
        if employee.max_capacity == 0:
            return 0.5
        
        utilization = employee.current_load / employee.max_capacity
        # Returns higher score for lower utilization
        return 1.0 - min(utilization, 1.0)

    def _log_decision(
        self,
        decision_type: str,
        entity_type: str,
        entity_id: int,
        input_data: Dict,
        decision_taken: str,
        confidence: float,
        reasoning: str
    ) -> None:
        """Log assignment decision for explainability."""
        log = DecisionLog(
            decision_type=decision_type,
            entity_type=entity_type,
            entity_id=entity_id,
            input_data=input_data,
            decision_taken=decision_taken,
            confidence=confidence,
            reasoning=reasoning
        )
        self.db.add(log)
