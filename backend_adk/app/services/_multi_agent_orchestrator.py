# app/services/_multi_agent_orchestrator.py

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core._logging import get_logger
from app.agents._intake_agent import IntakeAgent
from app.agents._planning_agent import PlanningAgent
from app.agents._risk_agent import RiskAgent
from app.agents._staffing_agent import StaffingAgent
from app.agents._execution_coordinator_agent import ExecutionCoordinatorAgent
from app.agents._communication_agent import CommunicationAgent
from app.agents._escalation_agent import EscalationAgent
from app.agents._project_observer_agent import ProjectObserverAgent
from app.agents._delivery_review_agent import DeliveryReviewAgent
from app.agents._rebalance_agent import RebalanceAgent
from app.agents._loop_communication_agent import LoopCommunicationAgent
from app.agents._loop_escalation_agent import LoopEscalationAgent
from app.models._agent_run import AgentRun
from app.models._audit_log import AuditLog
from app.models._communication import Communication
from app.models._decision_log import DecisionLog
from app.models._project import Project
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._task_dependency import TaskDependency
from app.models._workflow_run import WorkflowRun
from app.services._assignment_engine import AssignmentEngine

logger = get_logger(__name__)


class MultiAgentOrchestrator:
    """
    First real multi-agent layer for this repo.

    This service does not replace the existing stack yet.
    It wraps current capabilities into explicit agent roles, shared context,
    and persisted workflow runs so the system can evolve toward a proper
    autonomous project-management runtime.
    """

    def __init__(self, db: Session):
        self.db = db
        self.assignment_engine = AssignmentEngine(db)

    def run_intake_workflow(
        self,
        request_text: str,
        requested_by: int,
        budget: float = 0.0,
        priority: str = "medium",
        deadline: Optional[datetime] = None,
        persist_project: bool = False,
    ) -> WorkflowRun:
        logger.info(
            f"Starting intake workflow for user_id={requested_by}, "
            f"priority={priority}, budget={budget}, persist={persist_project}"
        )
        
        workflow = WorkflowRun(
            workflow_type="project_intake",
            status="running",
            requested_by=requested_by,
            input_payload={
                "request_text": request_text,
                "budget": budget,
                "priority": priority,
                "deadline": deadline.isoformat() if deadline else None,
                "persist_project": persist_project,
            },
            shared_context={"stages": ["intake", "planning", "staffing", "risk"]},
        )
        self.db.add(workflow)
        self.db.flush()
        
        logger.debug(f"Created workflow_run id={workflow.id}")

        shared_context: Dict[str, Any] = {
            "request_text": request_text,
            "budget": budget,
            "priority": priority,
            "deadline": deadline,
            "persist_project": persist_project,
            "workflow_run_id": workflow.id,
        }

        intake_result = IntakeAgent().run(shared_context)
        logger.info(f"IntakeAgent completed: confidence={intake_result.confidence:.2f}, requires_review={intake_result.requires_human_review}")
        self._record_agent_run(workflow.id, shared_context, intake_result)
        shared_context["parsed_brief"] = intake_result.output_payload["parsed_brief"]

        planning_result = PlanningAgent().run(shared_context)
        logger.info(f"PlanningAgent completed: confidence={planning_result.confidence:.2f}, tasks_planned={len(planning_result.output_payload.get('tasks', []))}")
        self._record_agent_run(workflow.id, {"parsed_brief": shared_context["parsed_brief"]}, planning_result)
        shared_context["execution_plan"] = planning_result.output_payload

        # Resolve tenant for this admin so project gets scoped correctly
        from app.models._user import User as _AdminUser
        _admin_user = self.db.query(_AdminUser).filter(_AdminUser.id == requested_by).first()
        _tenant_id = _admin_user.tenant_id if _admin_user else None
        shared_context["tenant_id"] = _tenant_id

        if persist_project:
            logger.info("Materializing project in database")
            project, sequence_to_task_id = self._materialize_project(
                requested_by=requested_by,
                execution_plan=planning_result.output_payload,
                budget=budget,
                priority=priority,
                deadline=deadline,
                tenant_id=_tenant_id,
            )
            workflow.project_id = project.id
            shared_context["project_id"] = project.id
            shared_context["sequence_to_task_id"] = sequence_to_task_id
            logger.info(f"Project created: id={project.id}, tasks={len(sequence_to_task_id)}")

        staffing_result = StaffingAgent(
            self.db,
            scoring_fn=self.assignment_engine._calculate_employee_score,
        ).run(shared_context)
        logger.info(f"StaffingAgent completed: confidence={staffing_result.confidence:.2f}")
        self._record_agent_run(workflow.id, {"execution_plan": shared_context["execution_plan"]}, staffing_result)
        shared_context["staffing"] = staffing_result.output_payload

        # Persist staffing recommendations into the project's custom_fields so the
        # admin dashboard can show the draft team and allow swap/remove/accept flows.
        if shared_context.get("project_id"):
            self._bridge_staffing_to_project(
                project_id=shared_context["project_id"],
                staffing_output=staffing_result.output_payload,
                admin_user_id=requested_by,
            )

        risk_result = RiskAgent().run(shared_context)
        logger.info(f"RiskAgent completed: confidence={risk_result.confidence:.2f}")
        self._record_agent_run(
            workflow.id,
            {
                "execution_plan": shared_context["execution_plan"],
                "staffing": shared_context["staffing"],
            },
            risk_result,
        )
        shared_context["risk"] = risk_result.output_payload

        execution_result = ExecutionCoordinatorAgent().run(shared_context)
        self._record_agent_run(
            workflow.id,
            {
                "execution_plan": shared_context["execution_plan"],
                "staffing": shared_context["staffing"],
                "risk": shared_context["risk"],
            },
            execution_result,
        )
        shared_context["execution_coordination"] = execution_result.output_payload
        if shared_context.get("project_id") and shared_context.get("sequence_to_task_id"):
            execution_persistence = self._materialize_assignment_offers(
                workflow_id=workflow.id,
                project_id=shared_context["project_id"],
                sequence_to_task_id=shared_context["sequence_to_task_id"],
                execution_coordination=execution_result.output_payload,
            )
            shared_context["execution_persistence"] = execution_persistence

        communication_result = CommunicationAgent().run(shared_context)
        self._record_agent_run(
            workflow.id,
            {
                "execution_plan": shared_context["execution_plan"],
                "execution_coordination": shared_context["execution_coordination"],
                "risk": shared_context["risk"],
            },
            communication_result,
        )
        shared_context["communications"] = communication_result.output_payload
        if shared_context.get("project_id"):
            self._materialize_communications(
                shared_context["project_id"],
                communication_result.output_payload,
            )

        escalation_result = EscalationAgent().run(shared_context)
        self._record_agent_run(
            workflow.id,
            {
                "risk": shared_context["risk"],
                "execution_coordination": shared_context["execution_coordination"],
                "staffing": shared_context["staffing"],
            },
            escalation_result,
        )
        shared_context["escalation"] = escalation_result.output_payload

        workflow.requires_human_review = any(
            result.requires_human_review
            for result in [
                intake_result,
                planning_result,
                staffing_result,
                risk_result,
                execution_result,
                communication_result,
                escalation_result,
            ]
        )
        workflow.status = "completed"
        workflow.completed_at = datetime.utcnow()
        workflow.shared_context = {
            "parallel_branches": ["staffing", "risk"],
            "project_id": shared_context.get("project_id"),
            "completed_stages": [
                "intake",
                "planning",
                "staffing",
                "risk",
                "execution_coordination",
                "communication",
                "escalation",
            ],
        }
        workflow.final_output = {
            "project_summary": {
                "title": planning_result.output_payload["project_title"],
                "summary": planning_result.output_payload["project_summary"],
                "complexity": planning_result.output_payload["project_complexity"],
            },
            "execution_plan": planning_result.output_payload,
            "staffing": staffing_result.output_payload,
            "risk": risk_result.output_payload,
            "execution_coordination": execution_result.output_payload,
            "execution_persistence": shared_context.get("execution_persistence"),
            "communications": communication_result.output_payload,
            "escalation": escalation_result.output_payload,
            "recommended_next_actions": self._recommended_next_actions(shared_context),
            "autonomy_status": (
                "needs_human_review" if workflow.requires_human_review else "can_continue_autonomously"
            ),
        }

        self.db.merge(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def get_workflow_run(self, workflow_run_id: int, tenant_id: Optional[int] = None) -> Optional[WorkflowRun]:
        from app.models._user import User as _User
        query = self.db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id)
        if tenant_id is not None:
            # WorkflowRun has no tenant_id column; scope through the requesting user's tenant
            tenant_user_ids = self.db.query(_User.id).filter(_User.tenant_id == tenant_id).subquery()
            query = query.filter(WorkflowRun.requested_by.in_(tenant_user_ids))
        return query.first()

    def list_workflow_runs(self, limit: int = 20, tenant_id: Optional[int] = None):
        from app.models._user import User as _User
        query = self.db.query(WorkflowRun)
        if tenant_id is not None:
            tenant_user_ids = self.db.query(_User.id).filter(_User.tenant_id == tenant_id).subquery()
            query = query.filter(WorkflowRun.requested_by.in_(tenant_user_ids))
        return query.order_by(WorkflowRun.created_at.desc()).limit(limit).all()

    def run_project_execution_loop(
        self,
        project_id: int,
        requested_by: int,
        persist_followup_messages: bool = True,
    ) -> WorkflowRun:
        workflow = WorkflowRun(
            workflow_type="project_execution_loop",
            status="running",
            requested_by=requested_by,
            project_id=project_id,
            input_payload={
                "project_id": project_id,
                "persist_followup_messages": persist_followup_messages,
            },
            shared_context={"stages": ["project_observation", "delivery_review", "rebalancing", "loop_communication", "loop_escalation"]},
        )
        self.db.add(workflow)
        self.db.flush()

        shared_context: Dict[str, Any] = {
            "project_id": project_id,
            "persist_followup_messages": persist_followup_messages,
            "workflow_run_id": workflow.id,
        }

        observer_result = ProjectObserverAgent(self.db).run(shared_context)
        self._record_agent_run(workflow.id, {"project_id": project_id}, observer_result)
        shared_context["project_state"] = observer_result.output_payload

        review_result = DeliveryReviewAgent(self.db).run(shared_context)
        self._record_agent_run(workflow.id, {"project_state": shared_context["project_state"]}, review_result)
        shared_context["delivery_review"] = review_result.output_payload

        rebalance_result = RebalanceAgent(self.db).run(shared_context)
        self._record_agent_run(
            workflow.id,
            {
                "project_state": shared_context["project_state"],
                "delivery_review": shared_context["delivery_review"],
            },
            rebalance_result,
        )
        shared_context["rebalance"] = rebalance_result.output_payload

        communication_result = LoopCommunicationAgent().run(shared_context)
        self._record_agent_run(
            workflow.id,
            {
                "project_state": shared_context["project_state"],
                "delivery_review": shared_context["delivery_review"],
                "rebalance": shared_context["rebalance"],
            },
            communication_result,
        )
        shared_context["communications"] = communication_result.output_payload
        if persist_followup_messages:
            self._materialize_loop_communications(project_id, communication_result.output_payload)

        escalation_result = LoopEscalationAgent().run(shared_context)
        self._record_agent_run(
            workflow.id,
            {
                "delivery_review": shared_context["delivery_review"],
                "rebalance": shared_context["rebalance"],
            },
            escalation_result,
        )
        shared_context["escalation"] = escalation_result.output_payload

        workflow.requires_human_review = any(
            result.requires_human_review
            for result in [observer_result, review_result, rebalance_result, communication_result, escalation_result]
        )
        workflow.status = "completed"
        workflow.completed_at = datetime.utcnow()
        workflow.shared_context = {
            "completed_stages": ["project_observation", "delivery_review", "rebalancing", "loop_communication", "loop_escalation"],
            "project_id": project_id,
        }
        workflow.final_output = {
            "project_state": observer_result.output_payload,
            "delivery_review": review_result.output_payload,
            "rebalance": rebalance_result.output_payload,
            "communications": communication_result.output_payload,
            "escalation": escalation_result.output_payload,
            "recommended_next_actions": self._loop_next_actions(shared_context),
            "autonomy_status": "needs_human_review" if workflow.requires_human_review else "can_continue_autonomously",
        }

        self.db.merge(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def approve_workflow_run(self, workflow_run_id: int, admin_id: int) -> Optional[WorkflowRun]:
        workflow = self.get_workflow_run(workflow_run_id)
        if not workflow:
            return None

        final_output = workflow.final_output or {}
        execution_coordination = final_output.get("execution_coordination") or {}
        sequence_to_task_id = self._task_sequence_map_for_project(workflow.project_id) if workflow.project_id else {}

        persistence = self._materialize_assignment_offers(
            workflow_id=workflow.id,
            project_id=workflow.project_id,
            sequence_to_task_id=sequence_to_task_id,
            execution_coordination=execution_coordination,
            include_review_required=True,
            approval_reason=f"Admin {admin_id} approved escalated workflow",
        ) if workflow.project_id else {
            "created_assignment_count": 0,
            "created_assignments": [],
            "skipped_existing_task_ids": [],
        }

        final_output["execution_persistence"] = persistence
        final_output["autonomy_status"] = "approved_for_execution"
        final_output["recommended_next_actions"] = [
            "Monitor assignment responses from approved tasks",
            "Track project health and rebalance if execution signals degrade",
            "Continue using the workbench for further approvals or follow-up loops",
        ]
        escalation = final_output.get("escalation") or {}
        escalation["decision"] = "approved_by_admin"
        escalation["approved_by"] = admin_id
        final_output["escalation"] = escalation

        workflow.requires_human_review = False
        workflow.shared_context = {
            **(workflow.shared_context or {}),
            "approval": {
                "approved_by": admin_id,
                "approved_at": datetime.utcnow().isoformat(),
            },
        }
        workflow.final_output = final_output

        self.db.add(
            AuditLog(
                action="workflow_approved",
                entity_type="workflow_run",
                entity_id=workflow.id,
                decision_reason="Admin approved escalated multi-agent workflow",
                performed_by="human",
                context_data={
                    "admin_id": admin_id,
                    "project_id": workflow.project_id,
                    "created_assignment_count": persistence["created_assignment_count"],
                },
            )
        )
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def _record_agent_run(self, workflow_run_id: int, input_payload: Dict[str, Any], result) -> None:
        run = AgentRun(
            workflow_run_id=workflow_run_id,
            agent_name=result.agent_name,
            role=result.role,
            stage=result.stage,
            status="completed",
            confidence=result.confidence,
            requires_human_review=result.requires_human_review,
            reasoning=result.reasoning,
            input_payload=self._json_safe(input_payload),
            output_payload=self._json_safe(result.output_payload),
            completed_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.flush()

    def _materialize_project(
        self,
        requested_by: int,
        execution_plan: Dict[str, Any],
        budget: float,
        priority: str,
        deadline: Optional[datetime],
        tenant_id: Optional[int] = None,
    ) -> tuple[Project, Dict[int, int]]:
        from datetime import timedelta as _td
        approval_deadline = (datetime.utcnow() + _td(minutes=240)).isoformat()
        project = Project(
            name=execution_plan["project_title"],
            description=execution_plan["project_summary"],
            admin_id=requested_by,
            tenant_id=tenant_id,
            budget=budget,
            priority=priority,
            deadline=deadline,
            status="planning",
            custom_fields={
                "current_phase": "intake",
                "approval_status": "awaiting-admin-approval",
                "approval_deadline": approval_deadline,
                "approval_window_minutes": 240,
                "next_decision": "Admin approval required for the AI-generated team draft and role plan",
                "recommended_team": [],
                "role_clusters": [],
                "team_invites": [],
                "team_join_deadline": None,
                "team_join_window_minutes": 240,
                "team_join_status": "pending-admin-approval",
                "replacement_suggestions": [],
                "emp_involved_ids": [],
                "report_text": None,
                "final_report": None,
                "payment_updates": [],
                "notifications": [],
                "project_complexity": execution_plan.get("project_complexity", 0.7),
                "planning_packet": {
                    "project_complexity": execution_plan.get("project_complexity", 0.7),
                    "project_summary": execution_plan.get("project_summary", ""),
                    "tasks": execution_plan.get("tasks", []),
                },
                "created_by_workflow": "project_intake",
            },
        )
        self.db.add(project)
        self.db.flush()

        sequence_to_task_id = {}
        for task_blueprint in execution_plan.get("tasks", []):
            task = Task(
                project_id=project.id,
                description=task_blueprint["title"],
                difficulty=task_blueprint["difficulty"],
                urgency=task_blueprint["urgency"],
                estimated_time=task_blueprint["estimated_time"],
                required_skills=task_blueprint["required_skills"],
                status="pending",
            )
            self.db.add(task)
            self.db.flush()
            sequence_to_task_id[task_blueprint["sequence"]] = task.id

        for dep in execution_plan.get("dependencies", []):
            task_id = sequence_to_task_id.get(dep["task_sequence"])
            depends_on_task_id = sequence_to_task_id.get(dep["depends_on_sequence"])
            if task_id and depends_on_task_id:
                self.db.add(
                    TaskDependency(
                        task_id=task_id,
                        depends_on_task_id=depends_on_task_id,
                        dependency_type=dep.get("dependency_type", "blocking"),
                    )
                )

        self.db.flush()
        return project, sequence_to_task_id

    def _bridge_staffing_to_project(
        self,
        project_id: int,
        staffing_output: Dict[str, Any],
        admin_user_id: int,
    ) -> None:
        """Convert StaffingAgent recommendations → project.custom_fields['recommended_team'].

        This makes the workbench-created project behave identically to a project
        created via create_project(), so the admin dashboard can show the draft team
        with swap/remove/accept controls.
        """
        from app.models._employee_profile import EmployeeProfile as _EP
        from app.models._user import User as _U
        from app.services._invite_service import get_or_create_project_team

        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        recommendations = staffing_output.get("staffing_recommendations", [])
        seen_ids: set = set()
        recommended_team = []

        for rec in recommendations:
            owner = rec.get("recommended_owner")
            if not owner:
                continue
            ep_id = owner.get("employee_profile_id")
            if not ep_id or ep_id in seen_ids:
                continue
            seen_ids.add(ep_id)

            ep = self.db.query(_EP).filter(_EP.id == ep_id).first()
            if not ep:
                continue
            user = self.db.query(_U).filter(_U.id == ep.user_id).first()

            # Derive role title from skills (mirrors _title_from_employee logic)
            skills = set((ep.skills or {}).keys())
            ROLE_SKILL_MAP = {
                "Solution Architect": ("architecture", "delivery"),
                "AI Engineer": ("llm", "modeling"),
                "Backend Engineer": ("backend", "api"),
                "Frontend Engineer": ("frontend", "react"),
                "QA Automation Engineer": ("qa", "testing", "automation"),
                "Delivery Lead": ("project-management",),
                "Client Success Manager": ("client-success", "reporting"),
                "DevOps Engineer": ("devops", "cloud", "security"),
                "Data Engineer": ("data", "analytics"),
                "Prompt Engineer": ("prompting", "research"),
            }
            best_title = ep.department or "AI Services"
            best_score = 0
            for title, markers in ROLE_SKILL_MAP.items():
                score = len(skills.intersection(set(markers)))
                if score > best_score:
                    best_title = title
                    best_score = score

            cap = ep.max_capacity or 8.0
            load = ep.current_load or 0.0
            workload_pct = round((load / cap) * 100) if cap > 0 else 0

            recommended_team.append({
                "employee_id": ep.id,
                "name": user.full_name if user else f"Employee {ep.id}",
                "title": best_title,
                "workload_percent": workload_pct,
                "task_title": rec.get("task_title"),
                "score": owner.get("score"),
            })

        # Build task_role_map: {str(task_id): role_title} so _assign_role_tasks_to_employee
        # can auto-assign tasks when each invited employee accepts their invite.
        ep_id_to_title = {member["employee_id"]: member["title"] for member in recommended_team}
        tasks_ordered = (
            self.db.query(Task)
            .filter(Task.project_id == project_id, Task.parent_task_id.is_(None))
            .order_by(Task.id.asc())
            .all()
        )
        seq_to_task_id = {idx + 1: task.id for idx, task in enumerate(tasks_ordered)}
        task_id_to_title = {task.id: task.title for task in tasks_ordered}

        task_role_map: dict = {}
        role_task_groups: dict = {}  # role_title -> [task_title]
        for rec in recommendations:
            owner = rec.get("recommended_owner")
            if not owner:
                continue
            ep_id = owner.get("employee_profile_id")
            seq = rec.get("task_sequence")
            task_id = seq_to_task_id.get(seq)
            role_title = ep_id_to_title.get(ep_id)
            if task_id and role_title:
                task_role_map[str(task_id)] = role_title
                role_task_groups.setdefault(role_title, []).append(task_id_to_title.get(task_id, f"Task {seq}"))

        role_clusters = [
            {"role": role, "task_titles": titles, "skills": [], "capacity_reasoning": "AI-drafted by staffing agent"}
            for role, titles in role_task_groups.items()
        ]

        meta = dict(project.custom_fields or {})
        meta["recommended_team"] = recommended_team
        meta["task_role_map"] = task_role_map
        meta["role_clusters"] = role_clusters

        # Mark as awaiting admin approval so the approval widget shows up
        if not meta.get("approval_status") or meta["approval_status"] == "awaiting-admin-approval":
            from datetime import timedelta as _td2
            meta["approval_status"] = "awaiting-admin-approval"
            meta["approval_deadline"] = (datetime.utcnow() + _td2(minutes=240)).isoformat()
            meta["next_decision"] = (
                f"Review the AI-drafted team of {len(recommended_team)} members and approve or swap before kickoff."
                if recommended_team
                else "No candidates found — ensure employees have correct skills and availability."
            )

        project.custom_fields = meta
        self.db.add(project)

        # Ensure a Team record exists for this project so team management APIs work
        get_or_create_project_team(self.db, project, admin_user_id)

        self.db.flush()
        logger.info(
            f"Bridged staffing → project {project_id}: {len(recommended_team)} team members written to custom_fields"
        )

    def _recommended_next_actions(self, shared_context: Dict[str, Any]):
        actions = list(shared_context["execution_coordination"]["next_actions"])
        persistence = shared_context.get("execution_persistence")
        if persistence and persistence.get("created_assignment_count", 0) > 0:
            actions.insert(
                0,
                f"Track {persistence['created_assignment_count']} persisted assignment offer(s) created by the orchestrator",
            )
        if shared_context["escalation"]["decision"] == "continue_autonomously":
            actions.insert(0, "Continue with autonomous assignment and coordination flow")
        else:
            actions.insert(0, "Open an admin review checkpoint using the escalation packet")
        return actions

    def _materialize_assignment_offers(
        self,
        workflow_id: int,
        project_id: int,
        sequence_to_task_id: Dict[int, int],
        execution_coordination: Dict[str, Any],
        include_review_required: bool = False,
        approval_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        created_assignments = []
        skipped_task_ids = []

        for item in execution_coordination.get("task_queue", []):
            if item.get("execution_mode") != "autonomous" and not include_review_required:
                continue

            task_id = sequence_to_task_id.get(item["task_sequence"])
            owner = item.get("recommended_owner")
            if not task_id or not owner:
                continue

            active = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task_id,
                TaskAssignment.status.in_(["pending", "accepted", "in-progress"]),
            ).first()
            if active:
                skipped_task_ids.append(task_id)
                continue

            assignment = TaskAssignment(
                task_id=task_id,
                employee_id=owner["employee_profile_id"],
                status="pending",
                estimated_hours=None,
                assignment_confidence=owner["score"],
                notes=f"Created by multi-agent workflow {workflow_id}",
            )
            self.db.add(assignment)
            self.db.flush()

            created_assignments.append(
                {
                    "assignment_id": assignment.id,
                    "task_id": task_id,
                    "employee_profile_id": owner["employee_profile_id"],
                    "confidence": owner["score"],
                }
            )

            self.db.add(
                DecisionLog(
                    decision_type="assignment",
                    entity_type="task",
                    entity_id=task_id,
                    input_data={
                        "workflow_id": workflow_id,
                        "execution_mode": item["execution_mode"],
                        "recommended_owner": owner,
                        "approval_reason": approval_reason,
                    },
                    decision_taken=f"Created assignment offer for employee profile {owner['employee_profile_id']}",
                    confidence=owner["score"],
                    reasoning=approval_reason or "Autonomous execution coordinator approved this task for assignment offer creation",
                )
            )
            self.db.add(
                AuditLog(
                    action="assignment_offer_created",
                    entity_type="task",
                    entity_id=task_id,
                    decision_reason="Created from multi-agent execution coordination stage",
                    performed_by="agent",
                    context_data={
                        "workflow_id": workflow_id,
                        "assignment_id": assignment.id,
                        "project_id": project_id,
                    },
                )
            )

        self.db.flush()
        return {
            "created_assignment_count": len(created_assignments),
            "created_assignments": created_assignments,
            "skipped_existing_task_ids": skipped_task_ids,
        }

    def _task_sequence_map_for_project(self, project_id: Optional[int]) -> Dict[int, int]:
        if not project_id:
            return {}
        tasks = self.db.query(Task).filter(Task.project_id == project_id).order_by(Task.id.asc()).all()
        return {index + 1: task.id for index, task in enumerate(tasks)}

    def _materialize_communications(self, project_id: int, communications_payload: Dict[str, Any]) -> None:
        admin_summary = communications_payload.get("admin_summary")
        delivery_results = communications_payload.get("delivery_results") or {}
        if admin_summary:
            self.db.add(
                Communication(
                    type=admin_summary["channel"],
                    from_actor="agent",
                    to_actor=admin_summary["audience"],
                    subject=admin_summary["subject"],
                    body=admin_summary["body"],
                    project_id=project_id,
                    task_id=None,
                    status="sent" if delivery_results.get("admin_summary") else "drafted",
                )
            )

        client_update = communications_payload.get("client_update_draft")
        if client_update:
            self.db.add(
                Communication(
                    type=client_update["channel"],
                    from_actor="agent",
                    to_actor=client_update["audience"],
                    subject=client_update["subject"],
                    body=client_update["body"],
                    project_id=project_id,
                    task_id=None,
                    status="sent" if delivery_results.get("client_update_draft") else "drafted",
                )
            )

        for message in communications_payload.get("assignment_messages", []):
            task_status = (delivery_results.get("assignment_messages") or {}).get(str(message.get("task_sequence")))
            self.db.add(
                Communication(
                    type=message["channel"],
                    from_actor="agent",
                    to_actor=message["audience"],
                    subject=message["subject"],
                    body=message["body"],
                    project_id=project_id,
                    task_id=None,
                    status="sent" if task_status else "drafted",
                )
            )
        self.db.flush()

    def _materialize_loop_communications(self, project_id: int, communications_payload: Dict[str, Any]) -> None:
        admin_followup = communications_payload.get("admin_followup")
        if admin_followup:
            self.db.add(
                Communication(
                    type="digest",
                    from_actor="agent",
                    to_actor="admin",
                    subject=admin_followup["subject"],
                    body=admin_followup["body"],
                    project_id=project_id,
                    task_id=None,
                    status="drafted",
                )
            )
        for message in communications_payload.get("recommended_messages", []):
            self.db.add(
                Communication(
                    type=message.get("type", "digest"),
                    from_actor="agent",
                    to_actor=message["audience"],
                    subject=f"Loop Follow-up: Project {project_id}",
                    body=message["body"],
                    project_id=project_id,
                    task_id=None,
                    status="drafted",
                )
            )
        self.db.flush()

    def _loop_next_actions(self, shared_context: Dict[str, Any]):
        actions = []
        risk_level = shared_context["delivery_review"]["risk_summary"]["risk_level"]
        if risk_level in ["high", "critical"]:
            actions.append("Escalate current delivery risks to the admin review queue")
        if shared_context["rebalance"]["reassignment_suggestions"]:
            actions.append("Review and apply reassignment suggestions for overloaded or mismatched tasks")
        if shared_context["rebalance"]["unassigned_active_tasks"]:
            actions.append("Create or approve assignment offers for unassigned active tasks")
        if not actions:
            actions.append("Continue autonomous monitoring and run the loop again after new execution signals arrive")
        return actions

    def _json_safe(self, value: Any):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: self._json_safe(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
