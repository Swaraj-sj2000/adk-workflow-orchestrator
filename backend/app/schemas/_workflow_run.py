# app/schemas/_workflow_run.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class MultiAgentIntakeRequest(BaseModel):
    request_text: str
    budget: float = 0.0
    priority: str = "medium"
    deadline: Optional[datetime] = None
    persist_project: bool = False


class MultiAgentLoopRequest(BaseModel):
    persist_followup_messages: bool = True


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    role: str
    stage: str
    status: str
    confidence: Optional[float]
    requires_human_review: bool
    reasoning: Optional[str]
    input_payload: Dict[str, Any]
    output_payload: Optional[Dict[str, Any]]
    started_at: datetime
    completed_at: Optional[datetime]


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_type: str
    status: str
    requested_by: int
    project_id: Optional[int]
    requires_human_review: bool
    input_payload: Dict[str, Any]
    shared_context: Optional[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime]
    agent_runs: List[AgentRunRead] = []
