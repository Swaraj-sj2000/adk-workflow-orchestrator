# app/agents/_intake_agent.py

from typing import Any, Dict

from app.agents._base import AgentResult, BaseAgent
from app.services._llm_service import LLMService


class IntakeAgent(BaseAgent):
    agent_name = "intake_agent"
    role = "project_intake"
    stage = "intake"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        llm = shared_context.get("llm_service") or LLMService()
        request_text = shared_context["request_text"]
        parsed = llm.parse_project_intake(request_text)
        used_llm = llm.enabled and parsed.get("project_title", "").strip() != request_text.strip().split(".")[0][:80]
        confidence = 0.85 if llm.enabled else 0.55
        reasoning = (
            "Used LLM to extract structured project plan from the brief"
            if llm.enabled
            else "LLM unavailable — used rule-based project plan from brief keywords"
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
