# app/services/_llm_service.py
import json
import os
import re
from typing import Any, Dict, List

from app.core._logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass

@dataclass
class HumanMessage:
    content: str

@dataclass
class SystemMessage:
    content: str

@dataclass
class _LLMResponse:
    content: str


# ── Gemini / Vertex AI backend ────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as _genai_types

    class _VertexChatModel:
        def __init__(
            self,
            model: str,
            project: str | None,
            location: str,
            temperature: float,
            max_output_tokens: int,
            timeout: int,
            api_key: str | None = None,
        ):
            self._model = model
            self._temperature = temperature
            self._max_output_tokens = max_output_tokens
            self._timeout = timeout
            if api_key:
                self._client = genai.Client(api_key=api_key)
            else:
                self._client = genai.Client(vertexai=True, project=project, location=location)

        def invoke(self, messages: List[Any]) -> _LLMResponse:
            system_parts: List[str] = []
            user_parts: List[str] = []
            for message in messages:
                text = str(getattr(message, "content", "")).strip()
                if not text:
                    continue
                if isinstance(message, SystemMessage):
                    system_parts.append(text)
                else:
                    user_parts.append(text)

            prompt = "\n\n".join([*system_parts, *user_parts]).strip()
            config = _genai_types.GenerateContentConfig(
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
            )
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return _LLMResponse(content=(getattr(response, "text", "") or "").strip())

    VERTEX_AVAILABLE = True
    logger.info("Google Vertex AI dependencies loaded successfully")
except ImportError:
    VERTEX_AVAILABLE = False
    _genai_types = None
    logger.warning("Google Vertex AI (google-genai) not available")


# ── HuggingFace backend (via InferenceClient chat completions) ────────────────
try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
    logger.info("HuggingFace InferenceClient loaded successfully")
except ImportError:
    HF_AVAILABLE = False
    InferenceClient = None
    logger.warning("huggingface-hub not available")


class _HFChatModel:
    """Uses HF InferenceClient chat_completion — works with all instruct/chat models."""

    def __init__(self, repo_id: str, token: str, temperature: float, max_new_tokens: int):
        self._client = InferenceClient(model=repo_id, token=token)
        self._temperature = temperature
        self._max_new_tokens = max_new_tokens

    def invoke(self, messages: List[Any]) -> _LLMResponse:
        hf_messages = []
        for message in messages:
            text = str(getattr(message, "content", "")).strip()
            if not text:
                continue
            role = "system" if isinstance(message, SystemMessage) else "user"
            hf_messages.append({"role": role, "content": text})

        response = self._client.chat_completion(
            messages=hf_messages,
            max_tokens=self._max_new_tokens,
            temperature=self._temperature,
        )
        content = response.choices[0].message.content or ""
        return _LLMResponse(content=content.strip())


class LLMService:
    """
    Multi-backend LLM service.

    Priority order:
      1. Gemini via Vertex AI  (GOOGLE_CLOUD_PROJECT + GOOGLE_GENAI_USE_VERTEXAI=true)
      2. Gemini via API key    (GOOGLE_API_KEY)
      3. HuggingFace endpoint  (HUGGINGFACEHUB_API_TOKEN) — local dev
      4. Deterministic fallback

    For Cloud Run / production: set GOOGLE_CLOUD_PROJECT and let Workload Identity handle auth.
    For local dev: set HUGGINGFACEHUB_API_TOKEN (and optionally HF_MODEL_ID).
    """

    def __init__(self):
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
        self.max_new_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))
        self.timeout = int(os.getenv("ADK_TIMEOUT", "60"))
        self.chat_model = None
        self.enabled = False
        self.backend = "none"

        # ── Priority 1: Vertex AI (production / Cloud Run) ────────────────────
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
        if project_id and use_vertex and VERTEX_AVAILABLE:
            try:
                model_id = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                location = os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("VERTEXAI_LOCATION", "us-central1"))
                self.chat_model = _VertexChatModel(
                    model=model_id, project=project_id, location=location,
                    temperature=self.temperature, max_output_tokens=self.max_new_tokens,
                    timeout=self.timeout,
                )
                self.enabled = True
                self.backend = f"gemini-vertex ({model_id})"
                logger.info(f"LLM backend: Vertex AI — {model_id} @ {project_id}/{location}")
            except Exception as exc:
                logger.error(f"Vertex AI init failed: {exc}", exc_info=True)

        # ── Priority 2: Gemini via API key (AI Studio / local) ────────────────
        if not self.enabled:
            api_key = os.getenv("GOOGLE_API_KEY", "")
            if api_key and VERTEX_AVAILABLE:
                try:
                    model_id = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                    self.chat_model = _VertexChatModel(
                        model=model_id, project=None, location="us-central1",
                        temperature=self.temperature, max_output_tokens=self.max_new_tokens,
                        timeout=self.timeout, api_key=api_key,
                    )
                    self.enabled = True
                    self.backend = f"gemini-apikey ({model_id})"
                    logger.info(f"LLM backend: Gemini API key — {model_id}")
                except Exception as exc:
                    logger.error(f"Gemini API key init failed: {exc}", exc_info=True)

        # ── Priority 3: HuggingFace endpoint (local dev) ──────────────────────
        if not self.enabled:
            hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
            if hf_token and HF_AVAILABLE:
                try:
                    hf_model = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")
                    self.chat_model = _HFChatModel(
                        repo_id=hf_model, token=hf_token,
                        temperature=self.temperature, max_new_tokens=self.max_new_tokens,
                    )
                    self.enabled = True
                    self.backend = f"huggingface ({hf_model})"
                    logger.info(f"LLM backend: HuggingFace — {hf_model}")
                except Exception as exc:
                    logger.error(f"HuggingFace init failed: {exc}", exc_info=True)

        if not self.enabled:
            logger.warning(
                "LLM service running in fallback mode — no backend configured. "
                "Set HUGGINGFACEHUB_API_TOKEN for local dev, "
                "or GOOGLE_CLOUD_PROJECT for Vertex AI / Cloud Run."
            )

    def _require_llm(self) -> None:
        if not self.enabled:
            raise RuntimeError(
                "LLM service is not configured. "
                "Set GOOGLE_CLOUD_PROJECT (Vertex AI / Cloud Run) or "
                "HUGGINGFACEHUB_API_TOKEN (local dev) before starting the service."
            )

    def parse_project_intake(self, request_text: str) -> Dict[str, Any]:
        logger.info(f"Parsing project intake request (length={len(request_text)} chars)")

        if self.enabled:
            try:
                messages = [
                    SystemMessage(content="You are an autonomous delivery planning agent. Output only the structured plan, no extra commentary."),
                    HumanMessage(
                        content=(
                            "Convert the project request below into EXACTLY this format. "
                            "Do not add any text before TITLE: or after the last TASK line.\n\n"
                            "TITLE: <concise project title>\n"
                            "SUMMARY: <2-sentence professional summary>\n"
                            "COMPLEXITY: <0.0 to 1.0>\n"
                            "PROJECT STRUCTURE: <key folders/services e.g. api/, frontend/, ml/>\n"
                            "TASK 1 TITLE: <title>\n"
                            "TASK 1 DESCRIPTION: <what this task delivers>\n"
                            "TASK 1 ROLE: <best role title>\n"
                            "TASK 1 DIFFICULTY: easy|medium|hard\n"
                            "TASK 1 URGENCY: low|medium|high|critical\n"
                            "TASK 1 HOURS: <integer>\n"
                            "TASK 1 SKILLS: skill=0.8, skill=0.7\n"
                            "TASK 1 OUTPUT: <deliverable>\n"
                            "SUBTASK 1.1 TITLE: <title>\n"
                            "SUBTASK 1.1 DETAILS: <specific file/module/API to create>\n"
                            "SUBTASK 1.1 HOURS: <integer>\n"
                            "SUBTASK 1.1 SKILLS: skill=0.8\n"
                            "SUBTASK 1.2 TITLE: <title>\n"
                            "SUBTASK 1.2 DETAILS: <specific file/module/API to create>\n"
                            "SUBTASK 1.2 HOURS: <integer>\n"
                            "SUBTASK 1.2 SKILLS: skill=0.8\n"
                            "Repeat the TASK block (with 2 SUBTASK lines each) for TASK 2 through TASK 5.\n\n"
                            "Rules: exactly 5 tasks, skills are decimal 0-1, hours are integers, "
                            "all field labels must be uppercase exactly as shown.\n\n"
                            f"Project request:\n{request_text}"
                        )
                    ),
                ]
                raw = self._invoke_text(messages)
                logger.debug(f"LLM intake raw output (first 500 chars): {raw[:500]}")
                parsed = self._parse_project_plan_text(raw)
                if parsed and len(parsed.get("tasks", [])) >= 3:
                    return self._normalize_project_payload(parsed, request_text)
                logger.warning("LLM project plan had < 3 tasks — falling back to rule-based intake")
            except Exception as exc:
                logger.error(f"LLM intake parse failed: {exc}", exc_info=True)

        return self._rule_based_project_intake(request_text)

    def _rule_based_project_intake(self, request_text: str) -> Dict[str, Any]:
        """Deterministic fallback: derives a reasonable 5-task plan from keywords in the brief."""
        text_lower = request_text.lower()
        title = request_text.strip().split(".")[0][:80] or "New Project"

        skill_map = {}
        if any(w in text_lower for w in ["react", "frontend", "ui", "dashboard", "interface"]):
            skill_map.update({"frontend": 0.85, "react": 0.8})
        if any(w in text_lower for w in ["api", "backend", "rest", "fastapi", "django", "flask"]):
            skill_map.update({"backend": 0.85, "api": 0.8})
        if any(w in text_lower for w in ["ml", "ai", "model", "predict", "train", "llm", "nlp"]):
            skill_map.update({"llm": 0.85, "modeling": 0.8})
        if any(w in text_lower for w in ["data", "pipeline", "etl", "ingest", "database", "crm"]):
            skill_map.update({"data": 0.85, "analytics": 0.75})
        if any(w in text_lower for w in ["deploy", "cloud", "docker", "kubernetes", "devops", "infra"]):
            skill_map.update({"devops": 0.85, "cloud": 0.8})
        if any(w in text_lower for w in ["test", "qa", "quality", "automation"]):
            skill_map.update({"qa": 0.8, "testing": 0.75})
        if not skill_map:
            skill_map = {"backend": 0.8, "project-management": 0.7}

        complexity = 0.65
        if any(w in text_lower for w in ["real-time", "microservice", "scale", "enterprise", "ml", "ai"]):
            complexity = 0.8
        if any(w in text_lower for w in ["simple", "basic", "prototype", "poc"]):
            complexity = 0.45

        task_templates = [
            {"title": "Requirements & Architecture", "description": "Define system requirements, data flow, and technical architecture.", "role": "Architect", "difficulty": "medium", "urgency": "high", "estimated_time": 16, "required_skills": {"architecture": 0.85, "delivery": 0.7}},
            {"title": "Core Backend Development", "description": "Build the primary server-side logic, data models, and APIs.", "role": "Backend Developer", "difficulty": "hard", "urgency": "high", "estimated_time": 40, "required_skills": {**({k: v for k, v in skill_map.items() if k in ("backend", "api", "python", "data")} or {"backend": 0.8})}},
            {"title": "AI / Data Layer", "description": "Implement ML models, data pipelines, or intelligent processing layer.", "role": "ML Engineer", "difficulty": "hard", "urgency": "high", "estimated_time": 32, "required_skills": {**({k: v for k, v in skill_map.items() if k in ("llm", "modeling", "data", "analytics")} or {"data": 0.8})}},
            {"title": "Frontend & User Interface", "description": "Build the user-facing dashboard, forms, and interactive components.", "role": "Frontend Developer", "difficulty": "medium", "urgency": "medium", "estimated_time": 24, "required_skills": {**({k: v for k, v in skill_map.items() if k in ("frontend", "react", "design-systems")} or {"frontend": 0.8})}},
            {"title": "Testing, QA & Deployment", "description": "Write automated tests, set up CI/CD, and deploy to production environment.", "role": "DevOps / QA Engineer", "difficulty": "medium", "urgency": "medium", "estimated_time": 20, "required_skills": {"qa": 0.8, "devops": 0.75, "testing": 0.7}},
        ]

        tasks = []
        for i, t in enumerate(task_templates, 1):
            tasks.append({**t, "sequence": i, "output": t["title"] + " deliverable", "subtasks": []})

        payload = {
            "project_title": title,
            "project_summary": f"{request_text[:200].rstrip()}. This plan covers architecture, backend, AI/data layer, frontend, and deployment.",
            "project_complexity": complexity,
            "project_structure": "backend/, frontend/, ml/, tests/, docs/",
            "tasks": tasks,
        }
        return self._normalize_project_payload(payload, request_text)

    def generate_client_update(self, context: Dict[str, Any]) -> str:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You write concise, professional project status updates for clients. "
                    "Be specific, calm, and outcome-oriented."
                )
            ),
            HumanMessage(
                content=(
                    "Draft an update under 180 words from this project context JSON.\n"
                    "Mention progress, active work, blockers if any, and the next checkpoint.\n\n"
                    f"{json.dumps(context)}"
                )
            ),
        ]
        result = self._invoke_text(messages)
        if not result:
            raise RuntimeError("LLM returned empty response for client update generation.")
        return result

    def generate_stage_brief(self, stage: str, audience: str, context: Dict[str, Any]) -> str:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an autonomous delivery manager. "
                    "Give concise operational guidance for the requested audience."
                )
            ),
            HumanMessage(
                content=(
                    f"Stage: {stage}\n"
                    f"Audience: {audience}\n"
                    "Write a short brief with:\n"
                    "- current objective\n"
                    "- recommendation\n"
                    "- fallback if approval is delayed or rejected\n"
                    "- immediate next step\n\n"
                    f"Context JSON:\n{json.dumps(context)}"
                )
            ),
        ]
        result = self._invoke_text(messages)
        if not result:
            raise RuntimeError("LLM returned empty response for stage brief generation.")
        return result

    def generate_decision_support(self, decision_type: str, audience: str, context: Dict[str, Any]) -> str:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an AI project director. "
                    "Give a recommendation that helps a human make the next decision with confidence."
                )
            ),
            HumanMessage(
                content=(
                    f"Decision type: {decision_type}\n"
                    f"Audience: {audience}\n"
                    "Return a concise decision memo with:\n"
                    "- recommendation\n"
                    "- why this is recommended\n"
                    "- what to watch next\n\n"
                    f"Context JSON:\n{json.dumps(context)}"
                )
            ),
        ]
        result = self._invoke_text(messages)
        if not result:
            raise RuntimeError("LLM returned empty response for decision support generation.")
        return result

    def generate_execution_package(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an execution planning agent for an autonomous delivery system. "
                    "Your job is to break down tasks into clear, traceable, actionable checkpoints."
                )
            ),
            HumanMessage(
                content=(
                    "Create a detailed execution package for the assigned contributor using this exact format:\n"
                    "SUMMARY: <one short paragraph>\n"
                    "CHECKPOINT 1: <specific title with implementation detail>\n"
                    "NOTES 1: <what to build, test, or clarify; include file/function names if relevant>\n"
                    "CHECKPOINT 2: <specific title>\n"
                    "NOTES 2: <details>\n"
                    "CHECKPOINT 3: <specific title>\n"
                    "NOTES 3: <details>\n"
                    "CHECKPOINT 4: <specific title>\n"
                    "NOTES 4: <details>\n"
                    "CHECKPOINT 5: <specific title>\n"
                    "NOTES 5: <details>\n"
                    "CHECKPOINT 6: <specific title>\n"
                    "NOTES 6: <details>\n\n"
                    "Rules:\n"
                    "- keep summary under 120 words\n"
                    "- create exactly 6 checkpoints\n"
                    "- each checkpoint must be specific enough that the contributor knows what to build or test\n"
                    "- include file names, function names, or test scenarios where relevant\n"
                    "- first checkpoint should clarify assumptions and dependencies\n"
                    "- last checkpoint should include validation and handoff readiness\n\n"
                    f"Context JSON:\n{json.dumps(context)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        payload = self._parse_execution_package(text)
        if not payload or "checkpoints" not in payload:
            raise RuntimeError("LLM returned an unparseable execution package. Check logs for raw output.")
        return payload

    def generate_concern_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._require_llm()
        messages = [
            SystemMessage(content="You are an AI delivery lead helping employees resolve concerns before escalating to admin."),
            HumanMessage(
                content=(
                    "Return this exact format:\n"
                    "RESPONSE: <short manager-like response>\n"
                    "ACTION: <immediate next action>\n"
                    "ESCALATE: yes|no\n"
                    "MEETING: yes|no\n\n"
                    f"Context JSON:\n{json.dumps(context)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        payload = self._parse_concern_response(text)
        if not payload:
            raise RuntimeError("LLM returned an unparseable concern response. Check logs for raw output.")
        return payload

    def suggest_blocker_resolution(self, blocker_context: Dict[str, Any]) -> str:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an operations copilot for an autonomous project system. "
                    "Suggest actions that reduce manager involvement while keeping control points clear."
                )
            ),
            HumanMessage(
                content=(
                    "Given this blocker context, propose 3 practical resolution options. "
                    "Keep them action-oriented and easy to execute.\n\n"
                    f"{json.dumps(blocker_context)}"
                )
            ),
        ]
        result = self._invoke_text(messages)
        if not result:
            raise RuntimeError("LLM returned empty response for blocker resolution.")
        return result

    def answer_user_question(
        self,
        message: str,
        role: str,
        user_name: str,
        live_context: str,
        platform_overview: str = "",
    ) -> str:
        self._require_llm()
        system = (
            f"You are the intelligent assistant embedded inside AI Workforce Orchestrator, "
            f"a B2B SaaS platform for AI-powered workforce management.\n\n"
            f"User: {user_name} | Role: {role}\n\n"
            f"Your job is to help this user understand the platform, navigate it, interpret their own data, "
            f"and take the right actions. You have access to their live account data below — use it to give "
            f"specific, accurate answers about their actual projects, tasks, team, and billing status.\n\n"
            f"Rules:\n"
            f"- Only discuss things relevant to this platform or the user's account data\n"
            f"- Never reveal data from other tenants or users outside this user's access scope\n"
            f"- Be concise and direct (3-5 sentences). Use bullet points for lists\n"
            f"- If asked something unrelated to the platform, politely redirect\n\n"
        )
        if platform_overview:
            system += f"PLATFORM KNOWLEDGE (features, navigation, roles):\n{platform_overview}\n\n"
        system += f"LIVE ACCOUNT DATA (scoped to this user's access):\n{live_context}"
        messages_list = [SystemMessage(content=system), HumanMessage(content=message)]
        result = self._invoke_text(messages_list)
        if not result:
            raise RuntimeError("LLM returned empty response for assistant chat.")
        return result

    def analyze_project_risks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an intelligent risk analysis agent for a software project delivery platform. "
                    "Analyze the project plan, staffing, and complexity to identify real risks. "
                    "Think critically — don't just check thresholds, reason about the actual situation."
                )
            ),
            HumanMessage(
                content=(
                    "Analyze this project context and return this exact format:\n"
                    "RISK_LEVEL: low|medium|high\n"
                    "NARRATIVE: <2-3 sentence paragraph explaining the overall risk picture>\n"
                    "RISK 1 TYPE: <category like staffing_gap, complexity, timeline, dependency, capacity>\n"
                    "RISK 1 SEVERITY: low|medium|high\n"
                    "RISK 1 REASON: <specific actionable reason>\n"
                    "RISK 2 TYPE: ...\n"
                    "RISK 2 SEVERITY: ...\n"
                    "RISK 2 REASON: ...\n"
                    "(up to 5 risks)\n\n"
                    "Rules:\n"
                    "- RISK_LEVEL should reflect the highest severity risk present\n"
                    "- Identify actual project-specific risks, not just generic ones\n"
                    "- If the team is overloaded, flag it as capacity risk with specific resolution hints\n"
                    "- If tasks have unclear skills or no available employees, flag as staffing risk\n"
                    "- Only include risks you can actually justify from the data\n\n"
                    f"Project context:\n{json.dumps(context, default=str)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        return self._parse_risk_analysis(text)

    def analyze_escalation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an intelligent escalation agent for an autonomous project management system. "
                    "Your goal is to minimize unnecessary human involvement while ensuring humans are "
                    "notified when the situation truly requires their judgment. The system's value comes "
                    "from running autonomously — only escalate when the AI cannot safely proceed alone."
                )
            ),
            HumanMessage(
                content=(
                    "Given this project state, decide whether to escalate to humans or continue autonomously.\n"
                    "Return this exact format:\n"
                    "DECISION: continue_autonomously|human_review_required\n"
                    "CONFIDENCE: <0.0 to 1.0>\n"
                    "NARRATIVE: <2-3 sentence reasoning for the decision>\n"
                    "REASON 1: <specific reason if escalating, or why it's safe to proceed if continuing>\n"
                    "REASON 2: ...\n"
                    "(up to 4 reasons)\n\n"
                    "Rules:\n"
                    "- Escalate only when: high risk + no clear mitigation, critical staffing gaps, "
                    "or execution cannot proceed safely without human input\n"
                    "- If all tasks have assigned owners with >65% confidence, prefer autonomous\n"
                    "- Weigh the cost of bothering a human vs the risk of proceeding alone\n"
                    "- Be specific about what the human needs to decide, not just that they should 'review'\n\n"
                    f"Project state:\n{json.dumps(context, default=str)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        return self._parse_escalation_analysis(text)

    def review_delivery_health(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an intelligent delivery review agent. Your job is to look at the current "
                    "project health, identify the most critical blockers, and recommend specific actions "
                    "that resolve them without requiring human intervention where possible."
                )
            ),
            HumanMessage(
                content=(
                    "Review this delivery health snapshot and return this exact format:\n"
                    "HEALTH_STATUS: on_track|at_risk|critical\n"
                    "NARRATIVE: <2-3 sentence paragraph on what's happening in this project right now>\n"
                    "PRIORITY ACTION 1: <the single most important action to unblock progress>\n"
                    "PRIORITY ACTION 2: <second most important action>\n"
                    "PRIORITY ACTION 3: <third action>\n"
                    "REQUIRES_HUMAN: yes|no\n"
                    "HUMAN_REASON: <if yes, explain exactly what needs human judgment>\n\n"
                    "Rules:\n"
                    "- Each priority action must be specific and executable (who does what)\n"
                    "- If employees are overloaded, suggest specific task redistribution\n"
                    "- If deadlines are at risk, suggest a specific adjustment\n"
                    "- Only mark REQUIRES_HUMAN=yes if no AI action can unblock the situation\n\n"
                    f"Delivery context:\n{json.dumps(context, default=str)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        return self._parse_delivery_review(text)

    def suggest_workload_rebalance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an intelligent workload rebalancing agent. The platform's core promise is "
                    "zero micromanagement — tasks flow smoothly, no employee burns out, deadlines are met. "
                    "When the workload is unbalanced or capacity is exceeded, you must propose concrete "
                    "redistribution strategies. The goal: maximum throughput, minimum stress, no project slippage."
                )
            ),
            HumanMessage(
                content=(
                    "Analyze this workload situation and return this exact format:\n"
                    "REBALANCE_NEEDED: yes|no\n"
                    "SEVERITY: low|medium|high|critical\n"
                    "NARRATIVE: <2-3 sentences on what the workload problem is and why it matters>\n"
                    "ACTION 1: <specific rebalancing action — e.g. reassign task X from employee A to B>\n"
                    "ACTION 2: <another action — e.g. split task Y into parallel subtasks>\n"
                    "ACTION 3: <another action — e.g. extend deadline by N days for task Z>\n"
                    "ACTION 4: <if applicable — e.g. flag that team needs 1 additional hire for skill X>\n"
                    "ADMIN_ALERT: yes|no\n"
                    "ADMIN_MESSAGE: <if yes, specific message to send the admin explaining what needs their decision>\n\n"
                    "Rules:\n"
                    "- If any employee is at 100%+ load, ALWAYS suggest specific redistribution\n"
                    "- Propose deadline extensions only when no redistribution is possible\n"
                    "- If the team lacks skills to complete tasks, recommend a specific hire or contractor\n"
                    "- Actions must be concrete: name employees and tasks, not generic advice\n"
                    "- The admin should only be contacted when the AI cannot self-resolve the imbalance\n\n"
                    f"Workload context:\n{json.dumps(context, default=str)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        return self._parse_rebalance_analysis(text)

    def generate_coordinator_actions(self, context: Dict[str, Any]) -> List[str]:
        self._require_llm()
        messages = [
            SystemMessage(
                content=(
                    "You are an execution coordinator agent. Given the project's execution queue, "
                    "staffing assignments, and risk level, generate the precise next actions the "
                    "system should take to move the project forward autonomously."
                )
            ),
            HumanMessage(
                content=(
                    "Generate a prioritized list of 4-6 specific next actions. Return one action per line, "
                    "each starting with ACTION: prefix.\n\n"
                    "Rules:\n"
                    "- Each action must be specific and executable (not generic platitudes)\n"
                    "- Order by priority (most critical first)\n"
                    "- Include which role (system/admin/employee) should take each action\n"
                    "- If high risk, first action must address the risk before any execution begins\n"
                    "- Mention specific task names or employee names from the context where relevant\n\n"
                    f"Execution context:\n{json.dumps(context, default=str)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        actions = []
        for line in text.split("\n"):
            line = line.strip()
            if line.lower().startswith("action:"):
                actions.append(line[7:].strip())
            elif line and not line.lower().startswith(("rule", "note", "context")):
                if len(line) > 10:
                    actions.append(line)
        return actions[:6] if actions else []

    def _parse_risk_analysis(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        risk_level_m = re.search(r"RISK_LEVEL:\s*(low|medium|high)", text, re.IGNORECASE)
        narrative_m = re.search(r"NARRATIVE:\s*(.+?)(?:\nRISK \d+ TYPE:|$)", text, re.DOTALL | re.IGNORECASE)
        risks = []
        for i in range(1, 6):
            type_m = re.search(rf"RISK {i} TYPE:\s*(.+?)(?:\nRISK {i} SEVERITY:|$)", text, re.DOTALL | re.IGNORECASE)
            sev_m = re.search(rf"RISK {i} SEVERITY:\s*(low|medium|high)", text, re.IGNORECASE)
            reason_m = re.search(rf"RISK {i} REASON:\s*(.+?)(?:\nRISK {i+1} TYPE:|$)", text, re.DOTALL | re.IGNORECASE)
            if type_m and sev_m and reason_m:
                risks.append({
                    "type": type_m.group(1).strip(),
                    "severity": sev_m.group(1).strip().lower(),
                    "reason": reason_m.group(1).strip(),
                })
        return {
            "risk_level": risk_level_m.group(1).strip().lower() if risk_level_m else "",
            "narrative": narrative_m.group(1).strip() if narrative_m else "",
            "risks": risks,
        }

    def _parse_escalation_analysis(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        decision_m = re.search(r"DECISION:\s*(continue_autonomously|human_review_required)", text, re.IGNORECASE)
        confidence_m = re.search(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
        narrative_m = re.search(r"NARRATIVE:\s*(.+?)(?:\nREASON \d+:|$)", text, re.DOTALL | re.IGNORECASE)
        reasons = []
        for i in range(1, 5):
            reason_m = re.search(rf"REASON {i}:\s*(.+?)(?:\nREASON {i+1}:|$)", text, re.DOTALL | re.IGNORECASE)
            if reason_m:
                reasons.append(reason_m.group(1).strip())
        return {
            "decision": decision_m.group(1).strip().lower() if decision_m else "",
            "confidence": float(confidence_m.group(1)) if confidence_m else 0.7,
            "narrative": narrative_m.group(1).strip() if narrative_m else "",
            "reasons": reasons,
        }

    def _parse_delivery_review(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        status_m = re.search(r"HEALTH_STATUS:\s*(on_track|at_risk|critical)", text, re.IGNORECASE)
        narrative_m = re.search(r"NARRATIVE:\s*(.+?)(?:\nPRIORITY ACTION \d+:|$)", text, re.DOTALL | re.IGNORECASE)
        actions = []
        for i in range(1, 4):
            action_m = re.search(rf"PRIORITY ACTION {i}:\s*(.+?)(?:\nPRIORITY ACTION {i+1}:|REQUIRES_HUMAN:|$)", text, re.DOTALL | re.IGNORECASE)
            if action_m:
                actions.append(action_m.group(1).strip())
        req_human_m = re.search(r"REQUIRES_HUMAN:\s*(yes|no)", text, re.IGNORECASE)
        human_reason_m = re.search(r"HUMAN_REASON:\s*(.+?)$", text, re.DOTALL | re.IGNORECASE)
        return {
            "health_status": status_m.group(1).strip().lower() if status_m else "",
            "narrative": narrative_m.group(1).strip() if narrative_m else "",
            "priority_actions": actions,
            "requires_human": req_human_m.group(1).lower() == "yes" if req_human_m else False,
            "human_reason": human_reason_m.group(1).strip() if human_reason_m else "",
        }

    def _parse_rebalance_analysis(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        needed_m = re.search(r"REBALANCE_NEEDED:\s*(yes|no)", text, re.IGNORECASE)
        severity_m = re.search(r"SEVERITY:\s*(low|medium|high|critical)", text, re.IGNORECASE)
        narrative_m = re.search(r"NARRATIVE:\s*(.+?)(?:\nACTION \d+:|$)", text, re.DOTALL | re.IGNORECASE)
        actions = []
        for i in range(1, 5):
            action_m = re.search(rf"ACTION {i}:\s*(.+?)(?:\nACTION {i+1}:|ADMIN_ALERT:|$)", text, re.DOTALL | re.IGNORECASE)
            if action_m:
                actions.append(action_m.group(1).strip())
        alert_m = re.search(r"ADMIN_ALERT:\s*(yes|no)", text, re.IGNORECASE)
        admin_msg_m = re.search(r"ADMIN_MESSAGE:\s*(.+?)$", text, re.DOTALL | re.IGNORECASE)
        return {
            "rebalance_needed": needed_m.group(1).lower() == "yes" if needed_m else False,
            "severity": severity_m.group(1).strip().lower() if severity_m else "low",
            "narrative": narrative_m.group(1).strip() if narrative_m else "",
            "actions": actions,
            "admin_alert": alert_m.group(1).lower() == "yes" if alert_m else False,
            "admin_message": admin_msg_m.group(1).strip() if admin_msg_m else "",
        }

    def _invoke_text(self, messages: List[Any]) -> str:
        try:
            logger.debug(f"Invoking LLM with {len(messages)} messages")
            response = self.chat_model.invoke(messages)
            result = getattr(response, "content", str(response)).strip()
            logger.debug(f"LLM response received (length={len(result)} chars)")
            return result
        except Exception as exc:
            logger.error(f"LLM invocation failed: {exc}", exc_info=True)
            return ""

    def _invoke_json(self, messages: List[Any]) -> Dict[str, Any]:
        text = self._invoke_text(messages)
        return self._parse_json(text)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    def _normalize_project_payload(self, payload: Dict[str, Any], request_text: str) -> Dict[str, Any]:
        tasks = []
        for item in payload.get("tasks", [])[:8]:
            tasks.append(
                {
                    "title": str(item.get("title") or "Task").strip(),
                    "description": str(item.get("description") or item.get("title") or "Task detail").strip(),
                    "difficulty": self._enum_value(item.get("difficulty"), {"easy", "medium", "hard"}, "medium"),
                    "urgency": self._enum_value(item.get("urgency"), {"low", "medium", "high", "critical"}, "medium"),
                    "estimated_time": max(1.0, float(item.get("estimated_time") or 8)),
                    "required_skills": self._normalize_skills(item.get("required_skills") or {}),
                    "required_role": str(item.get("required_role") or "").strip() or None,
                    "output": str(item.get("output") or "").strip() or None,
                    "subtasks": [
                        {
                            "title": str(subtask.get("title") or "Subtask").strip(),
                            "details": str(subtask.get("details") or subtask.get("title") or "").strip(),
                            "estimated_time": max(0.5, float(subtask.get("estimated_time") or 2)),
                            "required_skills": self._normalize_skills(subtask.get("required_skills") or item.get("required_skills") or {}),
                        }
                        for subtask in (item.get("subtasks") or [])[:6]
                        if subtask
                    ],
                }
            )

        if len(tasks) < 4:
            raise RuntimeError(
                f"LLM returned fewer than 4 tasks for request: {request_text[:80]!r}. "
                "Check LLM output in logs."
            )

        complexity = payload.get("project_complexity", 0.7)
        try:
            complexity = min(1.0, max(0.0, float(complexity)))
        except (TypeError, ValueError):
            complexity = 0.7

        return {
            "project_title": str(payload.get("project_title") or request_text[:80] or "Autonomous Project").strip(),
            "project_summary": str(payload.get("project_summary") or request_text).strip(),
            "project_complexity": complexity,
            "project_structure": str(payload.get("project_structure") or "").strip(),
            "tasks": tasks,
        }

    def _normalize_skills(self, skills: Dict[str, Any]) -> Dict[str, float]:
        normalized = {}
        for key, value in skills.items():
            try:
                normalized[str(key)] = min(1.0, max(0.0, float(value)))
            except (TypeError, ValueError):
                normalized[str(key)] = 0.6
        return normalized or {"project-management": 0.6}

    def _enum_value(self, value: Any, allowed: set, default: str) -> str:
        candidate = str(value or default).strip().lower()
        return candidate if candidate in allowed else default

    def _parse_execution_package(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}

        summary_match = re.search(r"SUMMARY:\s*(.+?)(?:\nCHECKPOINT 1:|$)", text, re.DOTALL | re.IGNORECASE)
        checkpoints = []
        for index in range(1, 7):  # Extended from 4 to 6 checkpoints
            title_match = re.search(
                rf"CHECKPOINT {index}:\s*(.+?)(?:\nNOTES {index}:|$)",
                text,
                re.DOTALL | re.IGNORECASE,
            )
            notes_match = re.search(
                rf"NOTES {index}:\s*(.+?)(?:\nCHECKPOINT {index + 1}:|$)",
                text,
                re.DOTALL | re.IGNORECASE,
            )
            if title_match and notes_match:
                checkpoints.append(
                    {
                        "title": title_match.group(1).strip(),
                        "notes": notes_match.group(1).strip(),
                    }
                )

        if len(checkpoints) < 4:  # Require at least 4 to be valid
            return {}

        return {
            "summary": summary_match.group(1).strip() if summary_match else "",
            "checkpoints": checkpoints,
        }

    def _parse_concern_response(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}

        response = re.search(r"RESPONSE:\s*(.+?)(?:\nACTION:|$)", text, re.DOTALL | re.IGNORECASE)
        action = re.search(r"ACTION:\s*(.+?)(?:\nESCALATE:|$)", text, re.DOTALL | re.IGNORECASE)
        escalate = re.search(r"ESCALATE:\s*(yes|no)", text, re.IGNORECASE)
        meeting = re.search(r"MEETING:\s*(yes|no)", text, re.IGNORECASE)

        if not response or not action or not escalate or not meeting:
            return {}

        return {
            "response": response.group(1).strip(),
            "action": action.group(1).strip(),
            "escalate": escalate.group(1).lower() == "yes",
            "meeting": meeting.group(1).lower() == "yes",
        }

    def _parse_project_plan_text(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}

        title_match = re.search(r"TITLE:\s*(.+?)(?:\nSUMMARY:|$)", text, re.DOTALL | re.IGNORECASE)
        summary_match = re.search(r"SUMMARY:\s*(.+?)(?:\nCOMPLEXITY:|$)", text, re.DOTALL | re.IGNORECASE)
        complexity_match = re.search(r"COMPLEXITY:\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
        structure_match = re.search(r"PROJECT STRUCTURE:\s*(.+?)(?:\nTASK 1 TITLE:|$)", text, re.DOTALL | re.IGNORECASE)

        tasks = []
        for index in range(1, 7):
            title = re.search(rf"TASK {index} TITLE:\s*(.+?)(?:\nTASK {index} DESCRIPTION:|$)", text, re.DOTALL | re.IGNORECASE)
            description = re.search(rf"TASK {index} DESCRIPTION:\s*(.+?)(?:\nTASK {index} ROLE:|$)", text, re.DOTALL | re.IGNORECASE)
            role = re.search(rf"TASK {index} ROLE:\s*(.+?)(?:\nTASK {index} DIFFICULTY:|$)", text, re.DOTALL | re.IGNORECASE)
            difficulty = re.search(rf"TASK {index} DIFFICULTY:\s*(easy|medium|hard)", text, re.IGNORECASE)
            urgency = re.search(rf"TASK {index} URGENCY:\s*(low|medium|high|critical)", text, re.IGNORECASE)
            hours = re.search(rf"TASK {index} HOURS:\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
            skills = re.search(rf"TASK {index} SKILLS:\s*(.+?)(?:\nTASK {index} OUTPUT:|$)", text, re.DOTALL | re.IGNORECASE)
            output = re.search(rf"TASK {index} OUTPUT:\s*(.+?)(?:\nSUBTASK {index}\.1 TITLE:|$)", text, re.DOTALL | re.IGNORECASE)

            if not title or not hours:
                continue

            skill_map = {}
            for skill_part in skills.group(1).split(","):
                if "=" not in skill_part:
                    continue
                key, value = skill_part.split("=", 1)
                try:
                    skill_map[key.strip()] = float(value.strip())
                except ValueError:
                    skill_map[key.strip()] = 0.6

            subtasks = []
            for sub_index in range(1, 7):
                next_marker = rf"\nSUBTASK {index}\.{sub_index + 1} TITLE:|\nTASK {index + 1} TITLE:|$"
                subtask_title = re.search(
                    rf"SUBTASK {index}\.{sub_index} TITLE:\s*(.+?)(?:\nSUBTASK {index}\.{sub_index} DETAILS:|$)",
                    text,
                    re.DOTALL | re.IGNORECASE,
                )
                subtask_details = re.search(
                    rf"SUBTASK {index}\.{sub_index} DETAILS:\s*(.+?)(?:\nSUBTASK {index}\.{sub_index} HOURS:|$)",
                    text,
                    re.DOTALL | re.IGNORECASE,
                )
                subtask_hours = re.search(
                    rf"SUBTASK {index}\.{sub_index} HOURS:\s*([0-9]*\.?[0-9]+)",
                    text,
                    re.IGNORECASE,
                )
                subtask_skills = re.search(
                    rf"SUBTASK {index}\.{sub_index} SKILLS:\s*(.+?)(?:{next_marker})",
                    text,
                    re.DOTALL | re.IGNORECASE,
                )
                if not all([subtask_title, subtask_details, subtask_hours, subtask_skills]):
                    continue

                subtask_skill_map = {}
                for skill_part in subtask_skills.group(1).split(","):
                    if "=" not in skill_part:
                        continue
                    key, value = skill_part.split("=", 1)
                    try:
                        subtask_skill_map[key.strip()] = float(value.strip())
                    except ValueError:
                        subtask_skill_map[key.strip()] = 0.6

                subtasks.append(
                    {
                        "title": subtask_title.group(1).strip(),
                        "details": subtask_details.group(1).strip(),
                        "estimated_time": float(subtask_hours.group(1).strip()),
                        "required_skills": subtask_skill_map,
                    }
                )

            tasks.append(
                {
                    "title": title.group(1).strip(),
                    "description": description.group(1).strip(),
                    "required_role": role.group(1).strip() if role else None,
                    "difficulty": difficulty.group(1).strip().lower(),
                    "urgency": urgency.group(1).strip().lower(),
                    "estimated_time": float(hours.group(1).strip()),
                    "required_skills": skill_map,
                    "output": output.group(1).strip() if output else None,
                    "subtasks": subtasks,
                }
            )

        if len(tasks) < 3:
            return {}

        return {
            "project_title": title_match.group(1).strip() if title_match else "",
            "project_summary": summary_match.group(1).strip() if summary_match else "",
            "project_complexity": float(complexity_match.group(1)) if complexity_match else 0.7,
            "project_structure": structure_match.group(1).strip() if structure_match else "",
            "tasks": tasks,
        }
