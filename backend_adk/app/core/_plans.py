"""
Central plan configuration for AI Workforce Orchestrator.

All monetary values are in Indian Rupees (INR).
Subscription is time-based: each plan grants access for a fixed number of days.
After expiry a grace period applies before auto-suspension kicks in.
"""

from __future__ import annotations

PLAN_CONFIG: dict[str, dict] = {
    "trial": {
        "display_name":      "Trial",
        "price_inr":         0,
        "billing_days":      30,        # subscription length
        "grace_days":        0,         # no grace — trial just expires
        "max_teams":         1,
        "max_projects":      3,
        "max_users":         5,
        "max_ai_calls":      50,
        "features": [
            "1 team",
            "3 projects",
            "5 users",
            "50 AI calls / month",
            "Community support",
        ],
    },
    "starter": {
        "display_name":      "Starter",
        "price_inr":         1_000,
        "billing_days":      30,
        "grace_days":        7,
        "max_teams":         10,
        "max_projects":      20,
        "max_users":         25,
        "max_ai_calls":      500,
        "features": [
            "10 teams",
            "20 projects",
            "25 users",
            "500 AI calls / month",
            "Email support",
            "Billing dashboard",
        ],
    },
    "pro": {
        "display_name":      "Pro",
        "price_inr":         5_000,
        "billing_days":      180,       # 6-month cycle
        "grace_days":        14,
        "max_teams":         -1,        # -1 = unlimited
        "max_projects":      -1,
        "max_users":         -1,
        "max_ai_calls":      5_000,
        "features": [
            "Unlimited teams",
            "Unlimited projects",
            "Unlimited users",
            "5,000 AI calls / month",
            "Priority support",
            "CEO dashboard",
            "Multi-agent workbench",
            "Audit logs",
        ],
    },
    "enterprise": {
        "display_name":      "Enterprise",
        "price_inr":         15_000,
        "billing_days":      365,       # annual
        "grace_days":        30,
        "max_teams":         -1,
        "max_projects":      -1,
        "max_users":         -1,
        "max_ai_calls":      -1,        # unlimited
        "features": [
            "Everything in Pro",
            "Unlimited AI calls",
            "Dedicated support",
            "Custom integrations",
            "SLA guarantee",
            "On-premise option",
        ],
    },
}


def get_plan(tier: str) -> dict:
    return PLAN_CONFIG.get(tier, PLAN_CONFIG["trial"])


def plan_display(tier: str) -> str:
    return get_plan(tier)["display_name"]


def is_unlimited(value: int) -> bool:
    return value == -1
