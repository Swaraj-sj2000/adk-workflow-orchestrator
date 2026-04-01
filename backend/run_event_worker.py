#!/usr/bin/env python3
"""
Standalone event worker for the multi-agent orchestrator.

Usage examples:
  python backend/run_event_worker.py
  python backend/run_event_worker.py --batch-size 5 --poll-interval 1.5
  python backend/run_event_worker.py --once
"""

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.services._event_service import run_event_worker_loop  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the event queue worker for the multi-agent orchestrator.")
    parser.add_argument("--batch-size", type=int, default=10, help="How many queued events to process per cycle.")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds to sleep between idle polling cycles.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process exactly one cycle and exit.",
    )
    args = parser.parse_args()

    print(
        f"[event-worker] starting batch_size={args.batch_size} "
        f"poll_interval={args.poll_interval} once={args.once}"
    )
    run_event_worker_loop(
        batch_size=args.batch_size,
        poll_interval_seconds=args.poll_interval,
        max_cycles=1 if args.once else None,
    )


if __name__ == "__main__":
    main()
