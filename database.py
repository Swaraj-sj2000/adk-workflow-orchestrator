"""
database.py — SQLite persistence layer
=======================================
Tables:
  users              — user profiles and preferences
  workflows          — one per instruction, linked to user
  tasks              — linked to workflow
  meetings           — linked to workflow
  documents          — linked to workflow
  workflow_cache     — exact-match cache on planner output
  workflow_templates — org-level reusable plans
  sessions           — maps session_id to user_id

All writes go through helper functions.
Agents never touch SQLite directly — they call memory.py which calls here.
"""

import sqlite3
import json
import logging
from datetime import datetime

DB_PATH = "/tmp/orchestrator.db"


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Creates all tables on cold start. Safe to call multiple times."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            email       TEXT UNIQUE NOT NULL,
            preferences TEXT DEFAULT '{}',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            user_input  TEXT NOT NULL,
            status      TEXT DEFAULT 'in_progress',
            created_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id          TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            title       TEXT NOT NULL,
            deadline    TEXT,
            priority    TEXT DEFAULT 'medium',
            status      TEXT DEFAULT 'open',
            created_at  TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE TABLE IF NOT EXISTS meetings (
            id           TEXT PRIMARY KEY,
            workflow_id  TEXT NOT NULL,
            user_id      TEXT NOT NULL,
            title        TEXT NOT NULL,
            datetime     TEXT,
            participants TEXT,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id          TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            title       TEXT NOT NULL,
            content     TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE TABLE IF NOT EXISTS workflow_cache (
            query_hash  TEXT PRIMARY KEY,
            user_input  TEXT NOT NULL,
            plan_json   TEXT NOT NULL,
            hit_count   INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflow_templates (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            trigger_key TEXT NOT NULL,
            plan_json   TEXT NOT NULL,
            use_count   INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_workflows_user
            ON workflows(user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_workflow
            ON tasks(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_meetings_workflow
            ON meetings(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_documents_workflow
            ON documents(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id);
    """)
    conn.commit()
    conn.close()
    _seed_templates()
    logging.info("[DB] Initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Template seeding — pre-load common workflow templates
# ---------------------------------------------------------------------------

def _seed_templates() -> None:
    """Seeds org-level templates if the table is empty."""
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM workflow_templates"
    ).fetchone()[0]
    conn.close()

    if count > 0:
        return  # already seeded

    templates = [
        {
            "id": "tmpl-001",
            "name": "Client Onboarding",
            "trigger_key": "onboard",
            "plan_json": json.dumps({
                "tasks": [
                    {"title": "Send welcome email and NDA to client",
                     "deadline_offset_days": 1, "priority": "high"},
                    {"title": "Set up client project folder and access permissions",
                     "deadline_offset_days": 2, "priority": "high"},
                    {"title": "Assign dedicated project manager and team",
                     "deadline_offset_days": 2, "priority": "high"},
                    {"title": "Create project tracking board with milestones",
                     "deadline_offset_days": 3, "priority": "medium"},
                ],
                "meetings": [
                    {"title": "Client Kickoff Meeting",
                     "offset_days": 3, "time": "10:00",
                     "participants": "Project Manager, Client Lead, Tech Lead"},
                    {"title": "Internal Team Alignment",
                     "offset_days": 1, "time": "14:00",
                     "participants": "Project Manager, Engineering Team"},
                ],
                "documents": [
                    {"title": "Client Onboarding Brief",
                     "description": "Project scope, objectives, timeline, and team contacts"},
                    {"title": "Project Charter",
                     "description": "Deliverables, success metrics, risk register"},
                ]
            })
        },
        {
            "id": "tmpl-002",
            "name": "Product Launch",
            "trigger_key": "product launch",
            "plan_json": json.dumps({
                "tasks": [
                    {"title": "Finalise product feature list and release notes",
                     "deadline_offset_days": 3, "priority": "high"},
                    {"title": "Coordinate QA sign-off across all platforms",
                     "deadline_offset_days": 5, "priority": "high"},
                    {"title": "Prepare marketing assets and press release",
                     "deadline_offset_days": 7, "priority": "medium"},
                    {"title": "Set up post-launch monitoring and alerts",
                     "deadline_offset_days": 7, "priority": "medium"},
                ],
                "meetings": [
                    {"title": "Launch Readiness Review",
                     "offset_days": 5, "time": "09:00",
                     "participants": "Product, Engineering, Marketing, QA"},
                    {"title": "Post-Launch Retrospective",
                     "offset_days": 14, "time": "14:00",
                     "participants": "Full Team"},
                ],
                "documents": [
                    {"title": "Launch Plan",
                     "description": "Go-to-market strategy, timeline, owner per workstream"},
                    {"title": "Release Notes",
                     "description": "Feature summary, known issues, upgrade instructions"},
                ]
            })
        },
        {
            "id": "tmpl-003",
            "name": "Team Setup",
            "trigger_key": "new team",
            "plan_json": json.dumps({
                "tasks": [
                    {"title": "Define team roles, responsibilities, and reporting structure",
                     "deadline_offset_days": 2, "priority": "high"},
                    {"title": "Set up communication channels and tools access",
                     "deadline_offset_days": 2, "priority": "high"},
                    {"title": "Create team onboarding documentation",
                     "deadline_offset_days": 4, "priority": "medium"},
                    {"title": "Schedule recurring team syncs and rituals",
                     "deadline_offset_days": 3, "priority": "medium"},
                ],
                "meetings": [
                    {"title": "Team Kickoff — Mission and Goals",
                     "offset_days": 3, "time": "10:00",
                     "participants": "All Team Members, Engineering Manager"},
                    {"title": "One-on-One Introductions",
                     "offset_days": 5, "time": "11:00",
                     "participants": "Team Lead, Individual Members"},
                ],
                "documents": [
                    {"title": "Team Charter",
                     "description": "Mission, values, working agreements, decision-making process"},
                    {"title": "Onboarding Guide",
                     "description": "Tools setup, key contacts, first-week checklist"},
                ]
            })
        },
    ]

    conn = get_connection()
    now = datetime.now().isoformat()
    for t in templates:
        conn.execute(
            """INSERT OR IGNORE INTO workflow_templates
               (id, name, trigger_key, plan_json, use_count, created_at)
               VALUES (?,?,?,?,0,?)""",
            (t["id"], t["name"], t["trigger_key"], t["plan_json"], now)
        )
    conn.commit()
    conn.close()
    logging.info("[DB] Templates seeded.")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_or_create_user(email: str, name: str = None) -> dict:
    email = email.lower().strip()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if row:
        conn.close()
        return dict(row)

    user_id = f"user-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    display_name = name or email.split("@")[0].replace(".", " ").title()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO users (id, name, email, preferences, created_at) VALUES (?,?,?,?,?)",
        (user_id, display_name, email, "{}", now)
    )
    conn.commit()
    conn.close()
    logging.info("[DB] New user created: %s", email)
    return {
        "id": user_id, "name": display_name,
        "email": email, "preferences": "{}", "created_at": now
    }


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_user_preference(user_id: str, key: str, value: str) -> None:
    conn = get_connection()
    row = conn.execute(
        "SELECT preferences FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    prefs = json.loads(row["preferences"]) if row else {}
    prefs[key] = value
    conn.execute(
        "UPDATE users SET preferences = ? WHERE id = ?",
        (json.dumps(prefs), user_id)
    )
    conn.commit()
    conn.close()


def get_user_preferences(user_id: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT preferences FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return json.loads(row["preferences"]) if row else {}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def link_session_to_user(session_id: str, user_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, user_id, created_at) VALUES (?,?,?)",
        (session_id, user_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_user_id_for_session(session_id: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return row["user_id"] if row else None


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

def insert_workflow(workflow_id: str, user_input: str, user_id: str) -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO workflows (id, user_id, user_input, status, created_at) VALUES (?,?,?,?,?)",
        (workflow_id, user_id, user_input, "in_progress", now)
    )
    conn.commit()
    conn.close()
    return {"id": workflow_id, "user_id": user_id,
            "user_input": user_input, "status": "in_progress"}


def update_workflow_status(workflow_id: str, status: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE workflows SET status = ? WHERE id = ?", (status, workflow_id)
    )
    conn.commit()
    conn.close()


def get_workflow(workflow_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_workflow_history(user_id: str, limit: int = 5) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, user_input, status, created_at
           FROM workflows WHERE user_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def insert_task(workflow_id: str, user_id: str, title: str,
                deadline: str, priority: str = "medium") -> dict:
    task_id = f"task-{datetime.now().strftime('%H%M%S%f')}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO tasks
           (id, workflow_id, user_id, title, deadline, priority, status, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (task_id, workflow_id, user_id, title, deadline, priority, "open", now)
    )
    conn.commit()
    conn.close()
    return {"id": task_id, "workflow_id": workflow_id, "title": title,
            "deadline": deadline, "priority": priority, "status": "open"}


def get_tasks_for_workflow(workflow_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE workflow_id = ?", (workflow_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------

def insert_meeting(workflow_id: str, user_id: str, title: str,
                   datetime_str: str, participants: str) -> dict:
    meeting_id = f"mtg-{datetime.now().strftime('%H%M%S%f')}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO meetings
           (id, workflow_id, user_id, title, datetime, participants, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (meeting_id, workflow_id, user_id, title, datetime_str, participants, now)
    )
    conn.commit()
    conn.close()
    return {"id": meeting_id, "workflow_id": workflow_id, "title": title,
            "datetime": datetime_str, "participants": participants}


def get_meetings_for_workflow(workflow_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM meetings WHERE workflow_id = ?", (workflow_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def insert_document(workflow_id: str, user_id: str,
                    title: str, content: str) -> dict:
    doc_id = f"doc-{datetime.now().strftime('%H%M%S%f')}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO documents
           (id, workflow_id, user_id, title, content, created_at)
           VALUES (?,?,?,?,?,?)""",
        (doc_id, workflow_id, user_id, title, content, now)
    )
    conn.commit()
    conn.close()
    return {"id": doc_id, "workflow_id": workflow_id,
            "title": title, "content": content}


def get_documents_for_workflow(workflow_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documents WHERE workflow_id = ?", (workflow_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def get_cached_plan(user_input: str) -> str | None:
    import hashlib
    query_hash = hashlib.md5(
        user_input.lower().strip().encode()
    ).hexdigest()
    conn = get_connection()
    row = conn.execute(
        "SELECT plan_json FROM workflow_cache WHERE query_hash = ?",
        (query_hash,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE workflow_cache SET hit_count = hit_count + 1 WHERE query_hash = ?",
            (query_hash,)
        )
        conn.commit()
    conn.close()
    return row["plan_json"] if row else None


def save_plan_to_cache(user_input: str, plan_json: str) -> None:
    import hashlib
    query_hash = hashlib.md5(
        user_input.lower().strip().encode()
    ).hexdigest()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO workflow_cache
           (query_hash, user_input, plan_json, hit_count, created_at)
           VALUES (?,?,?,0,?)""",
        (query_hash, user_input, plan_json, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def get_template_for_input(user_input: str) -> dict | None:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM workflow_templates"
    ).fetchall()
    conn.close()

    user_input_lower = user_input.lower()
    for row in rows:
        if row["trigger_key"].lower() in user_input_lower:
            conn = get_connection()
            conn.execute(
                "UPDATE workflow_templates SET use_count = use_count + 1 WHERE id = ?",
                (row["id"],)
            )
            conn.commit()
            conn.close()
            logging.info("[DB] Template match: %s", row["name"])
            return dict(row)
    return None


# ---------------------------------------------------------------------------
# Full status read
# ---------------------------------------------------------------------------

def get_full_workflow_status(workflow_id: str) -> dict:
    return {
        "workflow": get_workflow(workflow_id),
        "tasks": get_tasks_for_workflow(workflow_id),
        "meetings": get_meetings_for_workflow(workflow_id),
        "documents": get_documents_for_workflow(workflow_id),
    }
