# app/agents/_base.py

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentResult:
    agent_name: str
    role: str
    stage: str
    confidence: float
    reasoning: str
    output_payload: Dict[str, Any]
    requires_human_review: bool = False


class BaseAgent:
    agent_name = "base_agent"
    role = "base"
    stage = "base"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
