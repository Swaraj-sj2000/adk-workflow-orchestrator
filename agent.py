"""
AI Workflow Orchestrator — agent.py
=====================================
Multi-agent pipeline: intent → plan → execute → persist → report

Memory layers:
  Session  — ADK state dict, scoped to conversation
  User     — SQLite users table, persists across sessions
  Global   — workflow_templates table, shared org-level patterns
  Cache    — workflow_cache table, skips planner on repeated inputs

Agent pipeline:
  orchestrator (root_agent)
      └── workflow_pipeline (SequentialAgent)
              ├── planner_agent       — generates JSON plan (skipped on cache/template hit)
              ├── task_agent          — creates tasks in DB
              ├── scheduler_agent     — schedules meetings in DB
              ├── doc_agent           — writes and stores documents
              └── summary_agent       — reads DB, formats final report
"""

import os
import logging
import datetime
import google.cloud.logging
from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.tool_context import ToolContext

import memory

# ---------------------------------------------------------------------------
# Logging & environment
# ---------------------------------------------------------------------------
try:
    cloud_logging_client = google.cloud.logging.Client()
    cloud_logging_client.setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)

load_dotenv()
model_name = os.getenv("MODEL", "gemini-2.5-flash")

# Initialise DB schema on cold start
import database
database.init_db()


# ---------------------------------------------------------------------------
# TOOL 1 — identify_user
# Called by root_agent when user provides their email.
# Sets up the full user context in shared state.
# ---------------------------------------------------------------------------

def identify_user(tool_context: ToolContext, email: str) -> dict:
    """
    Identifies the user by email. Creates a new profile if first visit.
    Loads their workflow history and preferences into shared state.
    This is the foundation of user memory — called once per session.
    """
    session_id = tool_context.state.get("SESSION_ID",
                  f"sess-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    tool_context.state["SESSION_ID"] = session_id

    profile = memory.identify_user(email, session_id)

    # Write everything to shared state — all downstream agents can read this
    tool_context.state["USER_ID"] = profile["user_id"]
    tool_context.state["USER_NAME"] = profile["name"]
    tool_context.state["USER_EMAIL"] = profile["email"]
    tool_context.state["IS_RETURNING_USER"] = profile["is_returning"]
    tool_context.state["USER_HISTORY"] = profile["history_summary"]
    tool_context.state["USER_PREFERENCES"] = str(profile["preferences"])

    logging.info(
        "[Orchestrator] User identified: %s | returning=%s",
        email, profile["is_returning"]
    )

    return {
        "status": "success",
        "name": profile["name"],
        "is_returning": profile["is_returning"],
        "previous_workflows": len(profile["workflow_history"]),
    }


# ---------------------------------------------------------------------------
# TOOL 2 — save_user_intent
# Called after user provides their instruction.
# Runs cache/template resolution — may skip planner entirely.
# ---------------------------------------------------------------------------

def save_user_intent(tool_context: ToolContext, user_input: str) -> dict:
    """
    Saves the user's instruction and resolves the execution plan.

    Resolution order:
      1. Exact-match cache  → use cached plan, skip planner
      2. Template match     → use template with today's dates, skip planner
      3. Neither            → planner agent generates the plan

    Writes PLAN_SOURCE to state so the planner knows whether to run.
    """
    user_id = tool_context.state.get("USER_ID", "anonymous")
    workflow_id = f"wf-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    tool_context.state["USER_INPUT"] = user_input
    tool_context.state["WORKFLOW_ID"] = workflow_id

    # Create workflow record in DB
    memory.create_workflow(workflow_id, user_input, user_id)

    # Try to resolve plan without calling the planner LLM
    resolved_plan, source = memory.resolve_plan(user_input)

    if resolved_plan:
        # Cache or template hit — write plan directly to state
        # The planner agent's instruction checks PLAN_SOURCE and
        # returns the existing plan immediately if it's pre-resolved
        tool_context.state["execution_plan"] = resolved_plan
        tool_context.state["PLAN_SOURCE"] = source
        logging.info("[Orchestrator] Plan resolved from %s — skipping LLM planner", source)
    else:
        tool_context.state["PLAN_SOURCE"] = "llm"
        logging.info("[Orchestrator] No cached plan — planner will generate")

    return {
        "status": "success",
        "workflow_id": workflow_id,
        "plan_source": source,
        "cache_hit": source in ("cache", "template"),
    }


# ---------------------------------------------------------------------------
# TOOL 3 — create_task
# Called by task_agent, once per task.
# ---------------------------------------------------------------------------

def create_task(tool_context: ToolContext, title: str,
                deadline: str, priority: str = "medium") -> dict:
    """Creates a single task and persists it to the database."""
    workflow_id = tool_context.state.get("WORKFLOW_ID", "unknown")
    user_id = tool_context.state.get("USER_ID", "anonymous")
    try:
        task = memory.store_task(workflow_id, user_id, title, deadline, priority)
        logging.info("[TaskAgent] Created: %s", title)
        return {"status": "success", "task": task}
    except Exception as e:
        logging.error("[TaskAgent] Failed: %s", e)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# TOOL 4 — schedule_meeting
# Called by scheduler_agent, once per meeting.
# ---------------------------------------------------------------------------

def schedule_meeting(tool_context: ToolContext, title: str,
                     datetime_str: str, participants: str) -> dict:
    """Schedules a single meeting and persists it to the database."""
    workflow_id = tool_context.state.get("WORKFLOW_ID", "unknown")
    user_id = tool_context.state.get("USER_ID", "anonymous")
    try:
        meeting = memory.store_meeting(
            workflow_id, user_id, title, datetime_str, participants
        )
        logging.info("[SchedulerAgent] Scheduled: %s", title)
        return {"status": "success", "meeting": meeting}
    except Exception as e:
        logging.error("[SchedulerAgent] Failed: %s", e)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# TOOL 5 — generate_document
# Called by doc_agent, once per document.
# ---------------------------------------------------------------------------

def generate_document(tool_context: ToolContext,
                      title: str, content: str) -> dict:
    """Writes and stores a document in the database."""
    workflow_id = tool_context.state.get("WORKFLOW_ID", "unknown")
    user_id = tool_context.state.get("USER_ID", "anonymous")
    try:
        doc = memory.store_document(workflow_id, user_id, title, content)
        logging.info("[DocAgent] Generated: %s", title)
        return {"status": "success", "document": doc}
    except Exception as e:
        logging.error("[DocAgent] Failed: %s", e)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# TOOL 6 — get_workflow_status
# Called by summary_agent to compile the final report.
# ---------------------------------------------------------------------------

def get_workflow_status(tool_context: ToolContext) -> dict:
    """
    Reads the full workflow record from the database.
    Also caches the generated plan for future reuse if it came from the LLM.
    """
    workflow_id = tool_context.state.get("WORKFLOW_ID")
    plan_source = tool_context.state.get("PLAN_SOURCE", "llm")
    user_input = tool_context.state.get("USER_INPUT", "")
    execution_plan = tool_context.state.get("execution_plan", "")

    # If plan was LLM-generated, cache it for next time
    if plan_source == "llm" and execution_plan:
        memory.cache_plan(user_input, execution_plan)
        logging.info("[SummaryAgent] Plan cached for future reuse")

    try:
        result = memory.get_workflow_status(workflow_id)
        return result
    except Exception as e:
        logging.error("[SummaryAgent] Failed to fetch status: %s", e)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# AGENT 1 — Planner
# Checks PLAN_SOURCE first — if pre-resolved, returns existing plan immediately.
# Only calls LLM if PLAN_SOURCE is 'llm'.
# ---------------------------------------------------------------------------

planner_agent = Agent(
    name="planner",
    model=model_name,
    description="Converts a business instruction into a structured JSON execution plan.",
    instruction="""
    You are a senior business workflow planner.

    First, check the PLAN_SOURCE value:

    If PLAN_SOURCE is 'cache' or 'template':
    → The execution_plan is already available in state.
    → Simply output the existing execution_plan as-is. Do not modify it.
    → Add a note: "(Plan resolved from {PLAN_SOURCE} — no LLM generation needed)"

    If PLAN_SOURCE is 'llm':
    → Generate a new plan based on USER_INPUT and USER_HISTORY below.
    → Use the user's history to inform decisions — if they've done similar
      workflows before, keep consistency in structure and naming.
    → Output ONLY valid JSON, no markdown, no explanation:

    {
      "tasks": [
        {
          "title": "Specific actionable task title",
          "deadline": "YYYY-MM-DD",
          "priority": "high | medium | low"
        }
      ],
      "meetings": [
        {
          "title": "Meeting title",
          "datetime": "YYYY-MM-DD HH:MM",
          "participants": "Comma-separated roles"
        }
      ],
      "documents": [
        {
          "title": "Document title",
          "description": "What this document covers in one sentence"
        }
      ]
    }

    Requirements when generating new plan:
    - 3-4 specific tasks, not generic filler
    - 1-2 meetings with realistic future dates
    - 1-2 documents genuinely needed for this workflow
    - Deadlines within 14 days of today
    - Be domain-specific — use the user's exact context

    PLAN_SOURCE: { PLAN_SOURCE }
    USER_INPUT: { USER_INPUT }
    USER_HISTORY:
    { USER_HISTORY }
    """,
    output_key="execution_plan",
)


# ---------------------------------------------------------------------------
# AGENT 2 — Task Agent
# ---------------------------------------------------------------------------

task_agent = Agent(
    name="task_agent",
    model=model_name,
    description="Creates every task from the execution plan, one tool call per task.",
    instruction="""
    You are a task management specialist.

    Read the EXECUTION_PLAN. For every item in the "tasks" array,
    call the 'create_task' tool with:
      - title: task title
      - deadline: YYYY-MM-DD
      - priority: high, medium, or low

    Call the tool ONCE per task, in order. Do not skip any.
    After all calls complete, respond with:
    "✅ Created [N] tasks for { USER_NAME }."

    EXECUTION_PLAN:
    { execution_plan }
    """,
    tools=[create_task],
    output_key="tasks_result",
)


# ---------------------------------------------------------------------------
# AGENT 3 — Scheduler Agent
# ---------------------------------------------------------------------------

scheduler_agent = Agent(
    name="scheduler_agent",
    model=model_name,
    description="Schedules every meeting from the execution plan.",
    instruction="""
    You are a scheduling coordinator.

    Read the EXECUTION_PLAN. For every item in the "meetings" array,
    call the 'schedule_meeting' tool with:
      - title: meeting title
      - datetime_str: YYYY-MM-DD HH:MM
      - participants: participants string

    Call the tool ONCE per meeting, in order. Do not skip any.
    After all calls complete, respond with:
    "✅ Scheduled [N] meetings for { USER_NAME }."

    EXECUTION_PLAN:
    { execution_plan }
    """,
    tools=[schedule_meeting],
    output_key="meetings_result",
)


# ---------------------------------------------------------------------------
# AGENT 4 — Documentation Agent
# ---------------------------------------------------------------------------

doc_agent = Agent(
    name="doc_agent",
    model=model_name,
    description="Writes full document content and stores it for each document in the plan.",
    instruction="""
    You are a professional documentation writer.

    Read the EXECUTION_PLAN and USER_INPUT.

    For each document in the plan:
    1. Write the full content — professional, structured, 150-250 words
    2. Call 'generate_document' with title and the content you wrote

    Quality standards:
    - Use the user's specific context — no generic filler
    - Include clear sections with headings
    - Write as if this will actually be used by the team

    After all documents are generated, respond with:
    "✅ Generated [N] documents for { USER_NAME }."

    USER_INPUT: { USER_INPUT }
    EXECUTION_PLAN: { execution_plan }
    """,
    tools=[generate_document],
    output_key="docs_result",
)


# ---------------------------------------------------------------------------
# AGENT 5 — Summary Agent
# Reads from DB, shows user context, formats full report.
# ---------------------------------------------------------------------------

summary_agent = Agent(
    name="summary_agent",
    model=model_name,
    description="Fetches full workflow data from DB and presents structured final report.",
    instruction="""
    You are a workflow reporting specialist.

    Call the 'get_workflow_status' tool to retrieve everything stored
    for this workflow from the database.

    Then present the complete results in EXACTLY this format:

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ✅  WORKFLOW COMPLETE
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    👤  User     : { USER_NAME } ({ USER_EMAIL })
    📋  Request  : { USER_INPUT }
    🆔  Workflow : [workflow id from tool result]
    💾  Source   : { PLAN_SOURCE }
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📌  TASKS  ([count] created)
    ┌──────────────────────────────────────────────
    [For each task:]
    │  • [title]
    │    Deadline : [deadline]  Priority : [priority]  Status : [status]
    └──────────────────────────────────────────────

    📅  MEETINGS  ([count] scheduled)
    ┌──────────────────────────────────────────────
    [For each meeting:]
    │  • [title]
    │    When : [datetime]   Who : [participants]
    └──────────────────────────────────────────────

    📄  DOCUMENTS  ([count] generated)
    ┌──────────────────────────────────────────────
    [For each document:]
    │  • [title]
    │    [First 2 sentences of content]
    └──────────────────────────────────────────────

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    💾  Persisted to SQLite · 🚀  Google ADK + Gemini 2.5 Flash
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Use ONLY real data from the tool result. No placeholders in output.
    """,
    tools=[get_workflow_status],
    output_key="final_report",
)


# ---------------------------------------------------------------------------
# Sequential workflow pipeline
# ---------------------------------------------------------------------------

workflow_pipeline = SequentialAgent(
    name="workflow_pipeline",
    description="Full execution pipeline: plan → tasks → meetings → docs → report.",
    sub_agents=[
        planner_agent,
        task_agent,
        scheduler_agent,
        doc_agent,
        summary_agent,
    ],
)


# ---------------------------------------------------------------------------
# Root agent — entry point
# Handles two-turn onboarding: identify user → capture intent → execute
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="orchestrator",
    model=model_name,
    description=(
        "AI Workflow Orchestrator — converts business instructions into "
        "fully executed, database-backed workflows with user memory, "
        "session continuity, and plan caching."
    ),
    instruction="""
    You are an AI Workflow Orchestrator. You have memory — you remember
    users across sessions and learn from their history.

    STEP 1 — On first message, greet the user and ask for their email:

    "👋 Welcome to the AI Workflow Orchestrator.

    I turn business instructions into fully executed workflows —
    tasks, meetings, and documents — stored in a database and
    personalised to you over time.

    To get started and personalise your experience,
    what's your email address?"

    STEP 2 — When user provides their email:
    - Call 'identify_user' with their email
    - If they are a RETURNING user (is_returning=True), greet them
      personally: "Welcome back, [name]! You've run [N] workflows
      before. What would you like to execute today?"
    - If they are a NEW user: "Great to meet you, [name]!
      What workflow would you like me to execute?
      For example: 'Onboard a new client' or 'Plan a product launch'"

    STEP 3 — When user provides their instruction:
    - Call 'save_user_intent' with their exact instruction
    - If cache_hit is True in the response, tell them:
      "I recognise this workflow type — using a pre-built plan
       to save time. Executing now..."
    - If cache_hit is False, say:
      "Got it. Generating your custom workflow plan now..."
    - Then immediately hand off to 'workflow_pipeline'

    IMPORTANT:
    - Never skip the email step
    - Never try to execute the workflow yourself
    - Always call the tools in order: identify_user → save_user_intent → handoff
    """,
    tools=[identify_user, save_user_intent],
    sub_agents=[workflow_pipeline],
)
