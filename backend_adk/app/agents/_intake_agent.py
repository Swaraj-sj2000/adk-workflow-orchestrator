# app/agents/_intake_agent.py

from typing import Any, Dict

from app.agents._base import AgentResult, BaseAgent
from app.services._llm_service import LLMService


class IntakeAgent(BaseAgent):
    agent_name = "intake_agent"
    role = "project_intake"
    stage = "intake"

    def __init__(self):
        self.llm_service = LLMService()

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        request_text = shared_context["request_text"]
        parsed = self.llm_service.parse_project_intake(request_text)
        confidence = 0.85 if self.llm_service.enabled else 0.55
        reasoning = (
            "Used LLM-backed intake parsing"
            if self.llm_service.enabled
            else "Used deterministic fallback intake parsing because LLM integration is unavailable"
        )
        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning=reasoning,
            output_payload={"parsed_brief": parsed},
            requires_human_review=confidence < 0.6,
        )
