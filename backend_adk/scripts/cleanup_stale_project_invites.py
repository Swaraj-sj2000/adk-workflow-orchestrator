#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db._database import SessionLocal
from app.models import (
    _email_delivery_log,
    _platform_audit_log,
    _refresh_token,
    _scheduled_agent_job,
    _support_ticket,
    _tenant_settings,
    _user_preferences,
)
from app.models import (
    _agent,
    _agent_run,
    _audit_log,
    _availability,
    _blocker,
    _change_request,
    _checkpoint,
    _client_profile,
    _communication,
    _decision_log,
    _employee_metrics,
    _employee_profile,
    _event_queue,
    _meeting,
    _notification,
    _performance_point,
    _project,
    _skill_change_request,
    _task,
    _task_assignment,
    _task_dependency,
    _task_progress,
    _team,
    _team_invite,
    _team_invite_request,
    _team_size_request,
    _tenant,
    _user,
    _workflow_run,
)
from app.services._maintenance_service import cancel_stale_project_team_invites


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find and optionally cancel stale pending team invites that still point "
            "to soft-deleted projects."
        )
    )
    parser.add_argument("--tenant-id", type=int, help="Restrict cleanup to one tenant")
    parser.add_argument("--project-id", type=int, help="Restrict cleanup to one project")
    parser.add_argument("--limit", type=int, help="Only inspect or update the first N matches")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the cleanup. Without this flag the script runs in dry-run mode.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = cancel_stale_project_team_invites(
            db,
            tenant_id=args.tenant_id,
            project_id=args.project_id,
            limit=args.limit,
            apply=args.apply,
        )

        if not args.apply:
            db.rollback()
        else:
            db.commit()

        print(f"Matched stale invites: {result['matched']}")
        print(f"Updated invites: {result['updated']}")
        print(f"Mode: {'apply' if args.apply else 'dry-run'}")

        if result["invites"]:
            print("")
            print("Affected invites:")
            for row in result["invites"]:
                print(
                    f"- invite_id={row['invite_id']} tenant_id={row['tenant_id']} "
                    f"project_id={row['project_id']} project={row['project_name']!r} "
                    f"email={row['email']!r} status={row['status']} "
                    f"project_deleted_at={row['project_deleted_at']}"
                )
        else:
            print("")
            print("No stale deleted-project invites found.")

        if not args.apply:
            print("")
            print("Dry run only. Re-run with --apply to cancel the invites above.")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
