# app/api/routes/_multi_agent.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core._deps import get_current_user, get_db
from app.models._user import User
from app.schemas._workflow_run import MultiAgentIntakeRequest, MultiAgentLoopRequest, WorkflowRunRead
from app.services._multi_agent_orchestrator import MultiAgentOrchestrator

router = APIRouter(prefix="/multi-agent", tags=["Multi-Agent"])


@router.post("/workflows/intake", response_model=WorkflowRunRead)
def run_intake_workflow(
    payload: MultiAgentIntakeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can run multi-agent workflows")

    orchestrator = MultiAgentOrchestrator(db)
    return orchestrator.run_intake_workflow(
        request_text=payload.request_text,
        requested_by=current_user.id,
        budget=payload.budget,
        priority=payload.priority,
        deadline=payload.deadline,
        persist_project=payload.persist_project,
    )


@router.get("/workflows", response_model=list[WorkflowRunRead])
def list_workflows(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orchestrator = MultiAgentOrchestrator(db)
    return orchestrator.list_workflow_runs(limit=limit, tenant_id=current_user.tenant_id)


@router.get("/workflows/{workflow_run_id}", response_model=WorkflowRunRead)
def get_workflow(
    workflow_run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orchestrator = MultiAgentOrchestrator(db)
    workflow = orchestrator.get_workflow_run(workflow_run_id, tenant_id=current_user.tenant_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return workflow


@router.post("/workflows/{workflow_run_id}/approve", response_model=WorkflowRunRead)
def approve_workflow(
    workflow_run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can approve workflows")

    orchestrator = MultiAgentOrchestrator(db)
    workflow = orchestrator.approve_workflow_run(workflow_run_id, admin_id=current_user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return workflow


@router.post("/projects/{project_id}/loop", response_model=WorkflowRunRead)
def run_project_loop(
    project_id: int,
    payload: MultiAgentLoopRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can run project loops")

    orchestrator = MultiAgentOrchestrator(db)
    return orchestrator.run_project_execution_loop(
        project_id=project_id,
        requested_by=current_user.id,
        persist_followup_messages=payload.persist_followup_messages,
    )
