# app/services/_llm_service.py
import json
import os
import re
from typing import Any, Dict, List

from app.core._logging import get_logger

logger = get_logger(__name__)

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain dependencies loaded successfully")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    HumanMessage = None
    SystemMessage = None
    ChatHuggingFace = None
    HuggingFaceEndpoint = None
    logger.warning("LangChain dependencies not available - fallback mode will be used")


class LLMService:
    """
    LangChain + Hugging Face service with deterministic fallback.

    Notes:
    - Uses HuggingFaceEndpoint wrapped by ChatHuggingFace when available.
    - Keeps the system usable without an HF token for local/product demos.
    """

    def __init__(self):
        self.model_id = os.getenv("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.3")
        self.token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        self.timeout = int(os.getenv("HF_TIMEOUT_SECONDS", "60"))
        self.temperature = float(os.getenv("HF_TEMPERATURE", "0.2"))
        self.max_new_tokens = int(os.getenv("HF_MAX_NEW_TOKENS", "900"))
        self.enabled = bool(self.token and LANGCHAIN_AVAILABLE)
        self.chat_model = None
        self.init_error = None

        logger.info(
            f"Initializing LLM service: model={self.model_id}, "
            f"temperature={self.temperature}, max_tokens={self.max_new_tokens}, "
            f"timeout={self.timeout}s, enabled={self.enabled}"
        )

        if self.enabled:
            try:
                logger.debug(f"Connecting to HuggingFace endpoint: {self.model_id}")
                endpoint = HuggingFaceEndpoint(
                    repo_id=self.model_id,
                    huggingfacehub_api_token=self.token,
                    temperature=self.temperature,
                    max_new_tokens=self.max_new_tokens,
                    timeout=self.timeout,
                )
                self.chat_model = ChatHuggingFace(llm=endpoint)
                logger.info(f"LLM service initialized successfully with model: {self.model_id}")
            except Exception as exc:
                self.chat_model = None
                self.enabled = False
                self.init_error = str(exc)
                logger.error(f"Failed to initialize LLM service: {exc}", exc_info=True)
        else:
            logger.warning("LLM service disabled - using fallback mode (no token or LangChain unavailable)")

    def parse_project_intake(self, request_text: str) -> Dict[str, Any]:
        logger.info(f"Parsing project intake request (length={len(request_text)} chars)")
        
        if not self.enabled:
            logger.warning("LLM disabled - using fallback project parser")
            return self._fallback_project_parse(request_text)

        messages = [
            SystemMessage(
                content=(
                    "You are an autonomous delivery planning agent."
                )
            ),
            HumanMessage(
                content=(
                    "Convert the project request into this exact format:\n"
                    "TITLE: <title>\n"
                    "SUMMARY: <clean professional summary>\n"
                    "COMPLEXITY: <0 to 1>\n"
                    "PROJECT STRUCTURE: <repo or script structure guidance>\n"
                    "TASK 1 TITLE: <title>\n"
                    "TASK 1 DESCRIPTION: <description>\n"
                    "TASK 1 ROLE: <one primary role title>\n"
                    "TASK 1 DIFFICULTY: easy|medium|hard\n"
                    "TASK 1 URGENCY: low|medium|high|critical\n"
                    "TASK 1 HOURS: <number>\n"
                    "TASK 1 SKILLS: skill=0.8, skill=0.7\n"
                    "TASK 1 OUTPUT: <main deliverable>\n"
                    "SUBTASK 1.1 TITLE: <title>\n"
                    "SUBTASK 1.1 DETAILS: <exact implementation detail with script/file/folder hints>\n"
                    "SUBTASK 1.1 HOURS: <number>\n"
                    "SUBTASK 1.1 SKILLS: skill=0.8, skill=0.7\n"
                    "Repeat SUBTASK 1.2 to SUBTASK 1.4.\n"
                    "Repeat for TASK 2 to TASK 6.\n\n"
                    "Rules:\n"
                    "- produce exactly 6 tasks\n"
                    "- tasks must be specific to the project domain\n"
                    "- each task must name the primary role best suited for it\n"
                    "- each subtask must be concrete enough that an engineer knows which module, script, service, or document to create\n"
                    "- project structure should mention likely folders, scripts, services, or integration modules\n"
                    "- avoid generic labels like implementation setup unless the project truly needs that exact phase\n"
                    "- keep required_skills values between 0 and 1\n"
                    "- estimated_time is in hours\n"
                    "- project_complexity must be between 0 and 1\n"
                    "- summarize the request in clean professional English\n\n"
                    f"Project request:\n{request_text}"
                )
            ),
        ]

        parsed = self._parse_project_plan_text(self._invoke_text(messages))
        if not parsed or "tasks" not in parsed:
            return self._fallback_project_parse(request_text)

        return self._normalize_project_payload(parsed, request_text)

    def generate_client_update(self, context: Dict[str, Any]) -> str:
        if not self.enabled:
            return self._fallback_client_update(context)

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
        return self._invoke_text(messages) or self._fallback_client_update(context)

    def generate_stage_brief(self, stage: str, audience: str, context: Dict[str, Any]) -> str:
        if not self.enabled:
            return self._fallback_stage_brief(stage, audience, context)

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
        return self._invoke_text(messages) or self._fallback_stage_brief(stage, audience, context)

    def generate_decision_support(self, decision_type: str, audience: str, context: Dict[str, Any]) -> str:
        if not self.enabled:
            return self._fallback_decision_support(decision_type, audience, context)

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
        return self._invoke_text(messages) or self._fallback_decision_support(decision_type, audience, context)

    def generate_execution_package(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return self._fallback_execution_package(context)

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
                    "- break down each major task area into smaller, traceable steps\n"
                    "- first checkpoint should clarify assumptions and dependencies\n"
                    "- last checkpoint should include validation and handoff readiness\n"
                    "- make checkpoints sequential and interdependent when possible\n\n"
                    f"Context JSON:\n{json.dumps(context)}"
                )
            ),
        ]
        text = self._invoke_text(messages)
        payload = self._parse_execution_package(text)
        if not payload or "checkpoints" not in payload:
            return self._fallback_execution_package(context)
        return payload

    def generate_concern_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return self._fallback_concern_response(context)

        messages = [
            SystemMessage(
                content=(
                    "You are an AI delivery lead helping employees resolve concerns before escalating to admin."
                )
            ),
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
        return payload or self._fallback_concern_response(context)

    def suggest_blocker_resolution(self, blocker_context: Dict[str, Any]) -> str:
        if not self.enabled:
            return (
                "1. Re-scope the blocked task into a smaller deliverable.\n"
                "2. Add a backup owner with complementary skills.\n"
                "3. Move the deadline after the root blocker is cleared and inform the client early."
            )

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
        return self._invoke_text(messages) or (
            "1. Break the task into a smaller next step.\n"
            "2. Reassign or add a backup owner with the missing skill.\n"
            "3. Update the deadline and notify the admin/client before the slip grows."
        )

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
            return self._fallback_project_parse(request_text)

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

    def _fallback_project_parse(self, request_text: str) -> Dict[str, Any]:
        lower_text = (request_text or "").lower()
        if any(keyword in lower_text for keyword in {"cctv", "fire", "yolo", "camera", "alarm"}):
            return {
                "project_title": "CCTV Fire Detection and Alert Pipeline",
                "project_summary": (
                    "Build a camera-ingestion and fire-alert platform that captures CCTV streams, stores footage, "
                    "detects fire events, maps camera IDs to rooms, notifies responsible stakeholders by email, and triggers alarms."
                ),
                "project_complexity": 0.86,
                "project_structure": (
                    "Use services for stream_ingestion, detection, alerting, room_mapping, and monitoring. "
                    "Create scripts for model bootstrap, camera registration, email notification testing, and alarm simulation."
                ),
                "tasks": [
                    {
                        "title": "CCTV Stream Ingestion and Retention Service",
                        "description": "Create the pipeline that connects to local IP cameras, validates stream health, and stores footage for later retrieval.",
                        "difficulty": "hard",
                        "urgency": "high",
                        "estimated_time": 12,
                        "required_role": "Backend Engineer",
                        "required_skills": {"backend": 0.9, "python": 0.86, "api": 0.72},
                        "output": "Operational ingestion service with retention-ready storage hooks",
                        "subtasks": [
                            {
                                "title": "Stream connector service",
                                "details": "Create a `services/stream_ingestion.py` module to open local IP CCTV streams and validate reconnect logic.",
                                "estimated_time": 3,
                                "required_skills": {"backend": 0.88, "python": 0.84},
                            },
                            {
                                "title": "Video retention script",
                                "details": "Write a `scripts/save_camera_feed.py` or equivalent worker to persist rolling footage for future review.",
                                "estimated_time": 3,
                                "required_skills": {"backend": 0.82, "python": 0.8},
                            },
                            {
                                "title": "Camera registry API",
                                "details": "Define API endpoints and models for camera ID, room number, stream URL, and responsible contacts.",
                                "estimated_time": 3,
                                "required_skills": {"backend": 0.88, "api": 0.84},
                            },
                            {
                                "title": "Stream health logging",
                                "details": "Add structured logs and failure handling for dropped streams, invalid URLs, and storage failures.",
                                "estimated_time": 2,
                                "required_skills": {"backend": 0.72, "security": 0.58},
                            },
                        ],
                    },
                    {
                        "title": "Fire Detection Model Integration",
                        "description": "Integrate a YOLO-based fire detector, model-loading path, and inference pipeline for live frames.",
                        "difficulty": "hard",
                        "urgency": "high",
                        "estimated_time": 14,
                        "required_role": "AI Engineer",
                        "required_skills": {"llm": 0.55, "python": 0.84, "modeling": 0.92},
                        "output": "Fire detection inference service with confidence-based alert trigger",
                        "subtasks": [
                            {
                                "title": "Model bootstrap script",
                                "details": "Create `scripts/load_fire_model.py` to load the YOLO weights, warm the runtime, and validate inference inputs.",
                                "estimated_time": 3,
                                "required_skills": {"modeling": 0.9, "python": 0.82},
                            },
                            {
                                "title": "Inference service",
                                "details": "Build `services/fire_detection.py` to sample frames, run inference, and return structured fire-event payloads.",
                                "estimated_time": 4,
                                "required_skills": {"modeling": 0.94, "python": 0.84},
                            },
                            {
                                "title": "Threshold and false-positive tuning",
                                "details": "Define configuration for thresholds, debounce logic, and confidence filtering to reduce noisy alerts.",
                                "estimated_time": 3,
                                "required_skills": {"modeling": 0.84, "analytics": 0.68},
                            },
                            {
                                "title": "Detection event schema",
                                "details": "Document the fire-event payload fields needed by backend alerting and audit storage layers.",
                                "estimated_time": 2,
                                "required_skills": {"communication": 0.65, "backend": 0.62},
                            },
                        ],
                    },
                    {
                        "title": "Alerting, Alarm, and Responsible Contact Flow",
                        "description": "Trigger alerts by room and responsible person, send email notifications, and activate the alarm signal.",
                        "difficulty": "hard",
                        "urgency": "critical",
                        "estimated_time": 12,
                        "required_role": "Backend Engineer",
                        "required_skills": {"backend": 0.88, "api": 0.84, "communication": 0.62},
                        "output": "End-to-end alert workflow from detection event to email and alarm activation",
                        "subtasks": [
                            {
                                "title": "Room-to-owner lookup service",
                                "details": "Create a lookup module joining camera IDs, room numbers, and responsible emails from the management database.",
                                "estimated_time": 3,
                                "required_skills": {"backend": 0.86, "api": 0.8},
                            },
                            {
                                "title": "Email alert integration",
                                "details": "Implement `services/email_alerts.py` with templated alert messages and failure retries.",
                                "estimated_time": 3,
                                "required_skills": {"backend": 0.78, "communication": 0.74},
                            },
                            {
                                "title": "Alarm trigger adapter",
                                "details": "Add a hardware or simulated alarm trigger interface that can be called from validated fire events.",
                                "estimated_time": 3,
                                "required_skills": {"backend": 0.76, "security": 0.62},
                            },
                            {
                                "title": "Alert audit trail",
                                "details": "Store sent alerts, alarm activations, timestamps, and acknowledgement states for later review.",
                                "estimated_time": 2,
                                "required_skills": {"backend": 0.74, "data": 0.58},
                            },
                        ],
                    },
                    {
                        "title": "System Architecture and Integration Guardrails",
                        "description": "Define the end-to-end service boundaries, repo structure, integration contracts, and delivery checkpoints.",
                        "difficulty": "hard",
                        "urgency": "high",
                        "estimated_time": 8,
                        "required_role": "Solution Architect",
                        "required_skills": {"architecture": 0.94, "delivery": 0.84, "backend": 0.68},
                        "output": "Approved solution architecture and implementation guardrails",
                        "subtasks": [
                            {
                                "title": "Service boundary map",
                                "details": "Describe modules for ingestion, inference, alerting, admin operations, and client reporting.",
                                "estimated_time": 2,
                                "required_skills": {"architecture": 0.92, "delivery": 0.78},
                            },
                            {
                                "title": "Repo and folder blueprint",
                                "details": "Recommend the backend service layout, scripts folder, test layout, and integration config ownership.",
                                "estimated_time": 2,
                                "required_skills": {"architecture": 0.86, "backend": 0.7},
                            },
                            {
                                "title": "Acceptance checkpoints",
                                "details": "Define review gates for stream ingestion, model detection, alerting, and fail-safe behavior.",
                                "estimated_time": 2,
                                "required_skills": {"delivery": 0.84, "communication": 0.66},
                            },
                            {
                                "title": "Risk and fallback plan",
                                "details": "Document what happens if the model underperforms, streams fail, or alerting infrastructure becomes unavailable.",
                                "estimated_time": 1,
                                "required_skills": {"architecture": 0.8, "security": 0.62},
                            },
                        ],
                    },
                    {
                        "title": "Admin and Operations Dashboard Flow",
                        "description": "Expose the fire system status, camera health, alert state, and project delivery visibility in the admin experience.",
                        "difficulty": "medium",
                        "urgency": "medium",
                        "estimated_time": 10,
                        "required_role": "Frontend Engineer",
                        "required_skills": {"frontend": 0.9, "react": 0.88, "design-systems": 0.68},
                        "output": "Operational dashboard views for setup, monitoring, and alert review",
                        "subtasks": [
                            {
                                "title": "Camera health UI",
                                "details": "Build dashboard sections for camera status, room mapping, and stream health indicators.",
                                "estimated_time": 3,
                                "required_skills": {"frontend": 0.88, "react": 0.84},
                            },
                            {
                                "title": "Alert event panel",
                                "details": "Create views for live fire alerts, email dispatch state, and alarm activation history.",
                                "estimated_time": 3,
                                "required_skills": {"frontend": 0.86, "react": 0.84},
                            },
                            {
                                "title": "Configuration form flow",
                                "details": "Add forms for camera registration, room mapping, and responsible-party contact updates.",
                                "estimated_time": 2,
                                "required_skills": {"frontend": 0.84, "react": 0.8},
                            },
                            {
                                "title": "Status abstraction copy",
                                "details": "Write clear business-facing labels for setup, testing, monitoring, and alert readiness states.",
                                "estimated_time": 1,
                                "required_skills": {"communication": 0.7, "frontend": 0.58},
                            },
                        ],
                    },
                    {
                        "title": "Validation, Simulation, and Rollout Readiness",
                        "description": "Test the end-to-end fire detection flow and validate safe rollout behavior before handoff.",
                        "difficulty": "medium",
                        "urgency": "high",
                        "estimated_time": 9,
                        "required_role": "QA Automation Engineer",
                        "required_skills": {"qa": 0.92, "testing": 0.9, "automation": 0.82},
                        "output": "Verified detection-to-alert workflow with rollout checklist",
                        "subtasks": [
                            {
                                "title": "Detection simulation scenarios",
                                "details": "Write tests or simulation scripts for fire/no-fire cases, noisy frames, and broken stream conditions.",
                                "estimated_time": 3,
                                "required_skills": {"qa": 0.9, "automation": 0.82},
                            },
                            {
                                "title": "Alert delivery validation",
                                "details": "Verify that the correct room owners receive email alerts and that alarm triggers fire only on valid detections.",
                                "estimated_time": 2,
                                "required_skills": {"testing": 0.86, "communication": 0.62},
                            },
                            {
                                "title": "Failure-mode checklist",
                                "details": "Capture fail-safe expectations for stream outage, email delivery failure, and alarm adapter errors.",
                                "estimated_time": 2,
                                "required_skills": {"qa": 0.84, "security": 0.62},
                            },
                            {
                                "title": "Go-live readiness summary",
                                "details": "Prepare the final validation summary, open risks, and sign-off notes for rollout approval.",
                                "estimated_time": 1,
                                "required_skills": {"communication": 0.78, "testing": 0.7},
                            },
                        ],
                    },
                ],
            }

        base_tasks: List[Dict[str, Any]] = [
            {
                "title": "Requirements and Scope",
                "description": "Clarify business goals, constraints, users, and acceptance criteria.",
                "difficulty": "medium",
                "urgency": "high",
                "estimated_time": 8,
                "required_role": "Project Coordinator",
                "required_skills": {"project-management": 0.8, "communication": 0.7},
                "output": "Signed-off scope brief",
                "subtasks": [
                    {
                        "title": "Requirement intake notes",
                        "details": "Capture the business objective, users, success metrics, and hard constraints in a kickoff brief.",
                        "estimated_time": 2,
                        "required_skills": {"project-management": 0.8, "communication": 0.7},
                    },
                    {
                        "title": "Acceptance criteria draft",
                        "details": "Write the first acceptance checklist and unresolved assumptions list.",
                        "estimated_time": 2,
                        "required_skills": {"communication": 0.72, "delivery": 0.62},
                    },
                ],
            },
            {
                "title": "Solution Design",
                "description": "Define the architecture, workflow, review points, and delivery approach.",
                "difficulty": "hard",
                "urgency": "high",
                "estimated_time": 12,
                "required_role": "Solution Architect",
                "required_skills": {"architecture": 0.8, "backend": 0.6},
                "output": "Architecture blueprint",
                "subtasks": [
                    {
                        "title": "Architecture map",
                        "details": "Describe service boundaries, data flow, and integration points.",
                        "estimated_time": 3,
                        "required_skills": {"architecture": 0.8, "backend": 0.6},
                    },
                    {
                        "title": "Risk and dependency review",
                        "details": "List critical dependencies, fallback design decisions, and review gates.",
                        "estimated_time": 2,
                        "required_skills": {"delivery": 0.68, "architecture": 0.72},
                    },
                ],
            },
            {
                "title": "Implementation Setup",
                "description": "Prepare the product foundation, services, integrations, and environments.",
                "difficulty": "hard",
                "urgency": "medium",
                "estimated_time": 16,
                "required_role": "Backend Engineer",
                "required_skills": {"python": 0.8, "backend": 0.8, "devops": 0.6},
                "output": "Implementation-ready service foundation",
                "subtasks": [
                    {
                        "title": "Core service scaffolding",
                        "details": "Create the base modules, settings, and service entrypoints.",
                        "estimated_time": 3,
                        "required_skills": {"backend": 0.8, "python": 0.8},
                    },
                    {
                        "title": "Environment and integration setup",
                        "details": "Prepare environment config, dependency wiring, and integration placeholders.",
                        "estimated_time": 3,
                        "required_skills": {"backend": 0.72, "devops": 0.6},
                    },
                ],
            },
            {
                "title": "Workflow and UI Delivery",
                "description": "Build the user-facing flows and the key dashboard or operational controls.",
                "difficulty": "medium",
                "urgency": "medium",
                "estimated_time": 14,
                "required_role": "Frontend Engineer",
                "required_skills": {"frontend": 0.8, "react": 0.8, "design-systems": 0.6},
                "output": "Usable dashboard and workflow UI",
                "subtasks": [
                    {
                        "title": "Primary workflow screens",
                        "details": "Implement the main UI paths and state transitions for the relevant user roles.",
                        "estimated_time": 3,
                        "required_skills": {"frontend": 0.8, "react": 0.8},
                    },
                    {
                        "title": "Status and action components",
                        "details": "Add the key action panels, progress indicators, and status abstractions.",
                        "estimated_time": 2,
                        "required_skills": {"frontend": 0.74, "design-systems": 0.62},
                    },
                ],
            },
            {
                "title": "Validation and Rollout Readiness",
                "description": "Test the flow, capture risks, and prepare for stakeholder review.",
                "difficulty": "medium",
                "urgency": "high",
                "estimated_time": 10,
                "required_role": "QA Automation Engineer",
                "required_skills": {"qa": 0.7, "communication": 0.6},
                "output": "Validation report and rollout checklist",
                "subtasks": [
                    {
                        "title": "Workflow test pass",
                        "details": "Run targeted checks across the most important user journeys and integrations.",
                        "estimated_time": 3,
                        "required_skills": {"qa": 0.7, "testing": 0.68},
                    },
                    {
                        "title": "Rollout checklist",
                        "details": "Prepare go-live risks, rollback notes, and final stakeholder readiness summary.",
                        "estimated_time": 2,
                        "required_skills": {"communication": 0.6, "qa": 0.62},
                    },
                ],
            },
        ]

        return {
            "project_title": request_text[:80] if request_text else "Autonomous Project",
            "project_summary": request_text,
            "project_complexity": 0.7,
            "project_structure": "Use role-owned service modules, scripts, UI flows, and validation packs.",
            "tasks": base_tasks,
        }

    def _fallback_client_update(self, context: Dict[str, Any]) -> str:
        return (
            f"Project update for '{context.get('project_name', 'Project')}': "
            f"{context.get('completed_tasks', 0)} tasks are complete, "
            f"{context.get('in_progress_tasks', 0)} are currently active, and "
            f"{context.get('blocked_tasks', 0)} are blocked. "
            "The team is tracking the next checkpoint closely and we will share the next concrete milestone update soon."
        )

    def _fallback_stage_brief(self, stage: str, audience: str, context: Dict[str, Any]) -> str:
        project_name = context.get("project_name", "the project")
        if audience == "admin":
            return (
                f"Stage: {stage}. Objective: move {project_name} forward with minimal manual coordination. "
                "Recommendation: review the suggested team and approve if the scope, urgency, and client setup look correct. "
                "Fallback: if approval is delayed, follow up on missing dependencies and keep the project in planning. "
                "Next step: confirm the decision and monitor the first assigned tasks."
            )
        if audience == "employee":
            return (
                f"Stage: {stage}. Objective: understand your likely ownership area and expected kickoff readiness for {project_name}. "
                "Recommendation: review the task fit, confirm blockers early, and be ready to accept or request clarification. "
                "Fallback: if the plan is rejected or stalled, wait for the revised brief instead of starting unsupported work. "
                "Next step: check the task summary and the immediate delivery priority."
            )
        if audience == "client":
            return (
                f"Stage: {stage}. Objective: keep you informed while {project_name} moves from intake into execution. "
                "Recommendation: confirm any pending project details quickly so the team can begin with fewer revisions. "
                "Fallback: if a decision is delayed, the system will hold execution and surface the next required input. "
                "Next step: watch for the next status update and clarify any open requirements."
            )
        return (
            f"Stage: {stage}. Objective: keep {project_name} moving through the next delivery checkpoint. "
            "Recommendation: follow the current plan and surface blockers early. "
            "Fallback: if execution slips, re-evaluate staffing and deadlines. "
            "Next step: review the next decision and current task ownership."
        )

    def _fallback_decision_support(self, decision_type: str, audience: str, context: Dict[str, Any]) -> str:
        project_name = context.get("project_name", "the project")
        if decision_type == "team_approval" and audience == "admin":
            return (
                f"Recommendation: approve the kickoff plan for {project_name} if the team mix covers solutioning, build, and reporting. "
                "Why: the system has already prepared the first execution packet and can start without further PM handholding. "
                "Watch next: early task ownership, client response speed, and any overload signal."
            )
        if decision_type == "team_approval" and audience == "employee":
            return (
                f"Recommendation: accept the project plan for {project_name} if the scope matches your specialty and no hidden blocker exists. "
                "Why: early clarity reduces rework later. "
                "Watch next: concrete task expectations and the first technical checkpoint."
            )
        return (
            f"Recommendation: take the next decision for {project_name} based on scope fit, response timing, and current workload. "
            "Why: the system is optimized to reduce coordination overhead once the decision gate is cleared. "
            "Watch next: the next phase owner, deadline risk, and communication status."
        )

    def _fallback_execution_package(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a detailed execution package with 6+ actionable checkpoints.
        Each checkpoint should be specific and traceable.
        """
        task_name = context.get("task_name", "the assigned task")
        role = context.get("role", "the assigned owner")
        project_structure = context.get("project_structure", "")
        subtask_hints = context.get("subtask_hints") or []
        
        # Build checkpoints with more granular detail
        checkpoints = []
        
        # 1. Dependency & Assumption Clarification
        checkpoints.append({
            "title": "Clarify dependencies and assumptions",
            "notes": (
                "Before starting implementation: confirm environment access, required libraries/APIs, "
                "data dependencies, and any integration points. Document blockers if any exist."
            )
        })
        
        # 2-4. Expand subtask hints into specific implementation steps
        for idx, hint in enumerate(subtask_hints[:3], start=1):
            hint_title = hint.get("title", f"Core work {idx}")
            hint_notes = hint.get("notes", f"Complete {hint_title}")
            
            checkpoints.append({
                "title": f"Implement {hint_title}",
                "notes": hint_notes
            })
        
        # 5. Testing & Validation
        if len(subtask_hints) > 3:
            hint = subtask_hints[3]
            checkpoints.append({
                "title": f"Test {hint.get('title', 'core functionality')}",
                "notes": hint.get("notes", "Validate all functionality works as expected with basic test cases.")
            })
        else:
            checkpoints.append({
                "title": "Test and validate implementation",
                "notes": (
                    "Write unit tests or integration tests. Verify error handling. Test edge cases and failure scenarios. "
                    "Document test results."
                )
            })
        
        # 6. Documentation & Handoff
        checkpoints.append({
            "title": "Document and prepare for handoff",
            "notes": (
                "Update code comments, create deployment notes, document any workarounds or known issues, "
                "update configuration or setup files, and verify the code is review-ready."
            )
        })
        
        return {
            "summary": (
                f"You own {task_name} as {role}. Start by validating assumptions and dependencies, "
                f"then complete the implementation in sequence, test thoroughly, and prepare for handoff. "
                f"{project_structure if project_structure else ''}"
            ),
            "checkpoints": checkpoints,
        }

    def _fallback_concern_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        severity = str(context.get("severity", "medium")).lower()
        concern_text = str(context.get("description", "")).lower()
        should_escalate = severity in {"high", "critical"}
        
        # Provide more specific guidance for common concerns
        if any(keyword in concern_text for keyword in ["email", "test", "real", "production"]):
            return {
                "response": (
                    "Always start with test infrastructure first. Set up a test email account or use a sandbox SMTP service. "
                    "This prevents sending alerts to real users before validation is complete."
                ),
                "action": (
                    "1. Set up test email with dummy SMTP endpoint or mailtrap.io\n"
                    "2. Implement and test email sending locally\n"
                    "3. Validate templates and retry logic\n"
                    "4. Only integrate real email addresses after testing is complete and approved."
                ),
                "escalate": False,
                "meeting": False,
            }
        
        return {
            "response": (
                "Review the concern against the current task scope. If it requires a dependency or external decision, "
                "document it clearly and try the recommended next step first before escalating."
            ),
            "action": (
                "Clarify the missing dependency or assumption, update task notes with your finding, "
                "then ask for escalation only if it genuinely blocks your work."
            ),
            "escalate": should_escalate,
            "meeting": should_escalate,
        }

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

            if not all([title, description, difficulty, urgency, hours, skills]):
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

        if len(tasks) < 4:
            return {}

        return {
            "project_title": title_match.group(1).strip() if title_match else "",
            "project_summary": summary_match.group(1).strip() if summary_match else "",
            "project_complexity": float(complexity_match.group(1)) if complexity_match else 0.7,
            "project_structure": structure_match.group(1).strip() if structure_match else "",
            "tasks": tasks,
        }
