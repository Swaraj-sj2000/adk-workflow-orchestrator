# app/services/_decision_service.py
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from app.models._decision_log import DecisionLog
from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._task import Task
from app.schemas._decision_log import DecisionLogRead
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class DecisionService:
    """
    Manages decision logs for system explainability.
    Every AI decision is logged with reason, confidence, and impact.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Internal helper: build a SQLAlchemy filter that restricts decisions
    # to entities owned by `tenant_id`.  Works without a tenant_id column
    # on decision_logs by joining through the owning entity tables.
    # ------------------------------------------------------------------
    def _tenant_filter(self, tenant_id: int):
        """Return an OR-filter that restricts decisions to the given tenant."""
        project_ids = (
            self.db.query(Project.id)
            .filter(Project.tenant_id == tenant_id)
            .subquery()
        )
        task_ids = (
            self.db.query(Task.id)
            .filter(Task.tenant_id == tenant_id)
            .subquery()
        )
        employee_ids = (
            self.db.query(EmployeeProfile.id)
            .filter(EmployeeProfile.tenant_id == tenant_id)
            .subquery()
        )
        return or_(
            and_(DecisionLog.entity_type == "project",  DecisionLog.entity_id.in_(project_ids)),
            and_(DecisionLog.entity_type == "task",     DecisionLog.entity_id.in_(task_ids)),
            and_(DecisionLog.entity_type == "employee", DecisionLog.entity_id.in_(employee_ids)),
        )
    
    def log_decision(
        self,
        decision_type: str,
        entity_type: str,
        entity_id: int,
        input_data: Dict,
        decision_taken: str,
        confidence: float,
        reasoning: Optional[str] = None
    ) -> DecisionLog:
        """Log a system decision for audit and explainability."""
        decision_log = DecisionLog(
            decision_type=decision_type,
            entity_type=entity_type,
            entity_id=entity_id,
            input_data=input_data,
            decision_taken=decision_taken,
            confidence=confidence,
            reasoning=reasoning
        )
        self.db.add(decision_log)
        self.db.commit()
        self.db.refresh(decision_log)
        return decision_log
    
    def get_decision_history(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        decision_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[int] = None,
    ) -> List[DecisionLog]:
        """Get decision history with optional filters, scoped to tenant."""
        query = self.db.query(DecisionLog)

        # Always restrict to the caller's tenant when tenant_id is known
        if tenant_id is not None:
            query = query.filter(self._tenant_filter(tenant_id))

        if entity_type:
            query = query.filter(DecisionLog.entity_type == entity_type)

        if entity_id:
            query = query.filter(DecisionLog.entity_id == entity_id)

        if decision_type:
            query = query.filter(DecisionLog.decision_type == decision_type)

        return query.order_by(DecisionLog.created_at.desc()).offset(skip).limit(limit).all()

    def count_decision_history(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        decision_type: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> int:
        query = self.db.query(DecisionLog)

        if tenant_id is not None:
            query = query.filter(self._tenant_filter(tenant_id))

        if entity_type:
            query = query.filter(DecisionLog.entity_type == entity_type)

        if entity_id:
            query = query.filter(DecisionLog.entity_id == entity_id)

        if decision_type:
            query = query.filter(DecisionLog.decision_type == decision_type)

        return query.count()
    
    def get_low_confidence_decisions(
        self,
        threshold: float = 0.6,
        last_n_hours: int = 24,
        tenant_id: Optional[int] = None,
    ) -> List[DecisionLog]:
        """Find decisions with low confidence that might need review, scoped to tenant."""
        cutoff_time = datetime.utcnow() - timedelta(hours=last_n_hours)

        query = self.db.query(DecisionLog).filter(
            DecisionLog.confidence < threshold,
            DecisionLog.created_at >= cutoff_time,
        )
        if tenant_id is not None:
            query = query.filter(self._tenant_filter(tenant_id))

        return query.order_by(DecisionLog.confidence.asc()).all()
    
    def override_decision(
        self,
        decision_id: int,
        admin_id: int,
        override_reason: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> DecisionLog:
        """Mark a decision as overridden by admin (scoped to tenant)."""
        query = self.db.query(DecisionLog).filter(DecisionLog.id == decision_id)
        if tenant_id is not None:
            query = query.filter(self._tenant_filter(tenant_id))
        decision = query.first()
        
        if decision:
            decision.override_by_admin = admin_id
            if override_reason:
                decision.reasoning = f"OVERRIDE: {override_reason}"
            self.db.merge(decision)
            self.db.commit()
        
        return decision
    
    def get_decision_statistics(
        self,
        last_n_days: int = 7,
        tenant_id: Optional[int] = None,
    ) -> Dict:
        """Get analytics on system decisions, scoped to tenant."""
        cutoff_time = datetime.utcnow() - timedelta(days=last_n_days)

        query = self.db.query(DecisionLog).filter(DecisionLog.created_at >= cutoff_time)
        if tenant_id is not None:
            query = query.filter(self._tenant_filter(tenant_id))

        decisions = query.all()
        
        if not decisions:
            return self._empty_stats()
        
        total = len(decisions)
        by_type = {}
        by_entity = {}
        overridden = 0
        avg_confidence = 0.0
        
        for decision in decisions:
            # Count by type
            if decision.decision_type not in by_type:
                by_type[decision.decision_type] = 0
            by_type[decision.decision_type] += 1
            
            # Count by entity
            if decision.entity_type not in by_entity:
                by_entity[decision.entity_type] = 0
            by_entity[decision.entity_type] += 1
            
            # Count overrides
            if decision.override_by_admin:
                overridden += 1
            
            avg_confidence += decision.confidence
        
        avg_confidence /= total
        
        return {
            "total_decisions": total,
            "by_type": by_type,
            "by_entity": by_entity,
            "overridden_count": overridden,
            "override_percentage": (overridden / total * 100) if total > 0 else 0,
            "avg_confidence": round(avg_confidence, 2),
            "period_days": last_n_days,
            "automation_level": round((1 - overridden / total) * 100, 2) if total > 0 else 0
        }
    
    def _empty_stats(self) -> Dict:
        """Return empty statistics structure."""
        return {
            "total_decisions": 0,
            "by_type": {},
            "by_entity": {},
            "overridden_count": 0,
            "override_percentage": 0.0,
            "avg_confidence": 0.0,
            "period_days": 7,
            "automation_level": 0.0
        }
