# app/services/_llm_service.py
import json
import os
import re
from typing import Dict, Any, List

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_huggingface import HuggingFaceEndpoint
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatPromptTemplate = None
    HuggingFaceEndpoint = None


class LLMService:
    """
    Thin LLM layer for hackathon use:
    - Structured project parsing
    - Client update generation
    - Blocker resolution suggestion
    Falls back to deterministic behavior when HF token is not present.
    """

    def __init__(self):
        self.model_id = os.getenv("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.3")
        self.token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        self.enabled = bool(self.token and LANGCHAIN_AVAILABLE)
        self.llm = None

        if self.enabled:
            self.llm = HuggingFaceEndpoint(
                repo_id=self.model_id,
                huggingfacehub_api_token=self.token,
                temperature=0.2,
                max_new_tokens=900,
            )

    def parse_project_intake(self, request_text: str) -> Dict[str, Any]:
        if not self.enabled:
            return self._fallback_project_parse(request_text)

        prompt = ChatPromptTemplate.from_template(
            """
You are a project planning engine.
Convert the request into strict JSON only. No markdown.

Required JSON format:
{{
  "project_title": "string",
  "project_summary": "string",
  "project_complexity": 0.0,
  "tasks": [
    {{
      "title": "string",
      "description": "string",
      "difficulty": "easy|medium|hard",
      "urgency": "low|medium|high|critical",
      "estimated_time": number,
      "required_skills": {{"skill_name": 0.0}}
    }}
  ]
}}

Rules:
- 4 to 8 tasks
- required_skills values must be between 0 and 1
- estimated_time in hours
- project_complexity between 0 and 1

User request:
{request_text}
"""
        )

        raw = (prompt | self.llm).invoke({"request_text": request_text})
        parsed = self._parse_json(raw)

        if not parsed or "tasks" not in parsed:
            return self._fallback_project_parse(request_text)
        return parsed

    def generate_client_update(self, context: Dict[str, Any]) -> str:
        if not self.enabled:
            return self._fallback_client_update(context)

        prompt = ChatPromptTemplate.from_template(
            """
Draft a concise professional client update email from this project context.
Tone: confident, clear, no fluff.
Keep under 180 words.

Context JSON:
{context}
"""
        )
        return (prompt | self.llm).invoke({"context": json.dumps(context)})

    def suggest_blocker_resolution(self, blocker_context: Dict[str, Any]) -> str:
        if not self.enabled:
            return "Suggest splitting task scope, reassigning a backup engineer, and extending deadline by 1-2 days."

        prompt = ChatPromptTemplate.from_template(
            """
Given this blocker context, propose 3 practical resolution options.
Keep it action-oriented.

Blocker context:
{blocker_context}
"""
        )
        return (prompt | self.llm).invoke({"blocker_context": json.dumps(blocker_context)})

    def _parse_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    def _fallback_project_parse(self, request_text: str) -> Dict[str, Any]:
        base_tasks: List[Dict[str, Any]] = [
            {
                "title": "Requirements and Scope",
                "description": "Define scope, success criteria, and non-functional constraints.",
                "difficulty": "medium",
                "urgency": "high",
                "estimated_time": 8,
                "required_skills": {"business_analysis": 0.7, "documentation": 0.6},
            },
            {
                "title": "Backend Service Development",
                "description": "Build APIs, data models, and orchestration logic.",
                "difficulty": "hard",
                "urgency": "high",
                "estimated_time": 20,
                "required_skills": {"python": 0.8, "fastapi": 0.8, "sql": 0.6},
            },
            {
                "title": "Frontend Dashboard",
                "description": "Implement management dashboard and execution views.",
                "difficulty": "medium",
                "urgency": "medium",
                "estimated_time": 14,
                "required_skills": {"react": 0.8, "javascript": 0.8, "ui_ux": 0.6},
            },
            {
                "title": "LLM Integration",
                "description": "Wire project parsing and communication generation via LLM.",
                "difficulty": "hard",
                "urgency": "medium",
                "estimated_time": 12,
                "required_skills": {"llm": 0.8, "prompt_engineering": 0.7},
            },
            {
                "title": "Testing and Demo Readiness",
                "description": "Run smoke tests, stabilize flows, and prepare demo narrative.",
                "difficulty": "medium",
                "urgency": "high",
                "estimated_time": 10,
                "required_skills": {"testing": 0.7, "communication": 0.6},
            },
        ]

        return {
            "project_title": request_text[:80] if request_text else "Autonomous PM Project",
            "project_summary": request_text,
            "project_complexity": 0.7,
            "tasks": base_tasks,
        }

    def _fallback_client_update(self, context: Dict[str, Any]) -> str:
        return (
            f"Project update for '{context.get('project_name', 'Project')}': "
            f"{context.get('completed_tasks', 0)} tasks completed, "
            f"{context.get('in_progress_tasks', 0)} in progress, "
            f"{context.get('blocked_tasks', 0)} blocked. "
            "The team is actively working on pending items and we will share milestone updates as they close."
        )
