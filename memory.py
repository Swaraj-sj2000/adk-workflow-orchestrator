"""
memory.py — Memory layer for AI Workflow Orchestrator
======================================================
Sits between agent.py and database.py.
Handles all decisions about memory, caching, and user context.

Three memory types:
  Session memory   — ADK state dict, scoped to one conversation
  User memory      — SQLite users + workflows table, persists across sessions
  Global memory    — workflow_templates table, shared across all users

Agents never import database.py directly.
They call memory.py which decides what to read/write and where.
"""

import json
import logging
from datetime import datetime, timedelta

import database as db


# ---------------------------------------------------------------------------
# User identification and session linking
# ---------------------------------------------------------------------------

def identify_user(email: str, session_id: str) -> dict:
    """
    Gets or creates a user by email.
    Links their session_id to their user_id so subsequent calls
    in the same ADK session know who they are.
    Returns full user profile including history and preferences.
    """
    user = db.get_or_create_user(email)
    db.link_session_to_user(session_id, user["id"])

    history = db.get_user_workflow_history(user["id"], limit=5)
    preferences = db.get_user_preferences(user["id"])

    is_returning = len(history) > 0

    logging.info(
        "[Memory] User identified: %s | returning=%s | history=%d workflows",
        email, is_returning, len(history)
    )

    return {
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_returning": is_returning,
        "preferences": preferences,
        "workflow_history": history,
        "history_summary": _format_history(history),
    }


def get_user_for_session(session_id: str) -> dict | None:
    """Looks up a user by their ADK session ID."""
    user_id = db.get_user_id_for_session(session_id)
    if not user_id:
        return None
    user = db.get_user_by_id(user_id)
    if not user:
        return None
    history = db.get_user_workflow_history(user_id, limit=5)
    return {**user, "history_summary": _format_history(history)}


def _format_history(history: list[dict]) -> str:
    """Formats workflow history into a readable string for agent context."""
    if not history:
        return "No previous workflows."
    lines = []
    for w in history:
        date = w["created_at"][:10]
        status = w["status"]
        lines.append(f"  • [{date}] {w['user_input']} ({status})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plan resolution — cache → template → LLM (in that order)
# ---------------------------------------------------------------------------

def resolve_plan(user_input: str) -> tuple[str | None, str]:
    """
    Tries to resolve an execution plan without calling the planner LLM.
    Returns (plan_json_or_None, source) where source is one of:
      'cache'    — exact match found in workflow_cache
      'template' — fuzzy match found in workflow_templates
      'llm'      — nothing found, planner agent must generate the plan

    The caller (save_user_intent tool) writes the result to state
    so the pipeline can skip the planner if plan is already resolved.
    """

    # 1. Check exact-match cache first
    cached = db.get_cached_plan(user_input)
    if cached:
        logging.info("[Memory] Cache HIT for input: %s", user_input[:50])
        return cached, "cache"

    # 2. Check org-level templates
    template = db.get_template_for_input(user_input)
    if template:
        resolved = _resolve_template_dates(template["plan_json"])
        logging.info("[Memory] Template match: %s", template["name"])
        return resolved, "template"

    # 3. Nothing found — LLM must generate
    logging.info("[Memory] Cache MISS — planner will generate plan")
    return None, "llm"


def _resolve_template_dates(plan_json: str) -> str:
    """
    Templates store deadline_offset_days and meeting offset_days
    instead of hardcoded dates. This function resolves them to
    actual dates relative to today.
    """
    today = datetime.now()
    plan = json.loads(plan_json)

    for task in plan.get("tasks", []):
        offset = task.pop("deadline_offset_days", 7)
        task["deadline"] = (today + timedelta(days=offset)).strftime("%Y-%m-%d")

    for meeting in plan.get("meetings", []):
        offset = meeting.pop("offset_days", 3)
        time = meeting.pop("time", "10:00")
        meeting["datetime"] = (
            (today + timedelta(days=offset)).strftime("%Y-%m-%d") + f" {time}"
        )

    return json.dumps(plan)


def cache_plan(user_input: str, plan_json: str) -> None:
    """Saves a freshly generated plan to cache for future reuse."""
    db.save_plan_to_cache(user_input, plan_json)
    logging.info("[Memory] Plan cached for input: %s", user_input[:50])


# ---------------------------------------------------------------------------
# Workflow creation
# ---------------------------------------------------------------------------

def create_workflow(workflow_id: str, user_input: str, user_id: str) -> dict:
    return db.insert_workflow(workflow_id, user_input, user_id)


# ---------------------------------------------------------------------------
# Task / Meeting / Document persistence
# ---------------------------------------------------------------------------

def store_task(workflow_id: str, user_id: str, title: str,
               deadline: str, priority: str = "medium") -> dict:
    return db.insert_task(workflow_id, user_id, title, deadline, priority)


def store_meeting(workflow_id: str, user_id: str, title: str,
                  datetime_str: str, participants: str) -> dict:
    return db.insert_meeting(workflow_id, user_id, title, datetime_str, participants)


def store_document(workflow_id: str, user_id: str,
                   title: str, content: str) -> dict:
    return db.insert_document(workflow_id, user_id, title, content)


# ---------------------------------------------------------------------------
# Status retrieval
# ---------------------------------------------------------------------------

def get_workflow_status(workflow_id: str) -> dict:
    result = db.get_full_workflow_status(workflow_id)
    db.update_workflow_status(workflow_id, "complete")
    return result


def get_user_history(user_id: str) -> list[dict]:
    return db.get_user_workflow_history(user_id, limit=10)
