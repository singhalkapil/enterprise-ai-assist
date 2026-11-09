"""Regulatory & Compliance Knowledge MCP Server.

Provides tools for national self-exclusion registry checks and jurisdictional bonus limits.
"""

from __future__ import annotations

from typing import Any, Dict
from enterprise_assist.mcp.client import MCPHub


class MockExclusionRegistry:
    """Mock registry simulating GAMSTOP (UK) and DGE (US-NJ) exclusion databases."""

    EXCLUDED_PLAYERS = {
        "PLY_EXCLUDED_UK": {"jurisdiction": "UKGC", "registry": "GAMSTOP", "excluded_since": "2025-01-15"},
        "PLY_EXCLUDED_NJ": {"jurisdiction": "US_NJ", "registry": "NJ_DGE_SELF_EXCLUSION", "excluded_since": "2025-06-20"},
    }


def check_jurisdiction_exclusion(player_id: str, jurisdiction: str) -> dict[str, Any]:
    """Check whether a player is enrolled in a statutory self-exclusion registry."""
    if player_id in MockExclusionRegistry.EXCLUDED_PLAYERS:
        entry = MockExclusionRegistry.EXCLUDED_PLAYERS[player_id]
        return {
            "player_id": player_id,
            "is_excluded": True,
            "registry": entry["registry"],
            "jurisdiction": entry["jurisdiction"],
            "action_required": "IMMEDIATE_ACCOUNT_BLOCK",
        }
    return {
        "player_id": player_id,
        "is_excluded": False,
        "jurisdiction": jurisdiction,
        "status": "CLEAR_TO_PLAY",
    }


def validate_bonus_entitlement(player_id: str, bonus_amount_usd: float, jurisdiction: str) -> dict[str, Any]:
    """Verify that an offered loyalty or retention bonus complies with regional caps."""
    # UKGC prohibits high unmonitored VIP retention bonuses (> $500 requires explicit AML affordability check)
    if jurisdiction == "UKGC" and bonus_amount_usd > 500.0:
        return {
            "eligible": False,
            "reason": "UKGC LCCP 3.4.3: Bonuses over $500 require verified affordability documentation.",
            "requires_human_approval": True,
        }

    # US_NJ DGE limits single promotional credits to $1,000 without supervisory sign-off
    if jurisdiction == "US_NJ" and bonus_amount_usd > 1000.0:
        return {
            "eligible": False,
            "reason": "US-NJ DGE Division Order 13: Promotional credits exceeding $1,000 require Compliance Director sign-off.",
            "requires_human_approval": True,
        }

    return {
        "eligible": True,
        "bonus_amount_usd": bonus_amount_usd,
        "jurisdiction": jurisdiction,
        "requires_human_approval": False,
    }


def register_regulatory_tools(hub: MCPHub) -> None:
    """Register all compliance tools to the MCP hub."""
    hub.register_tool(
        name="check_jurisdiction_exclusion",
        description="Check national statutory exclusion databases (GAMSTOP, DGE self-exclusion).",
        server_name="regulatory_mcp",
        handler=check_jurisdiction_exclusion,
        parameters={"player_id": "string", "jurisdiction": "string"},
    )
    hub.register_tool(
        name="validate_bonus_entitlement",
        description="Verify retention bonuses against strict UKGC and US-NJ jurisdictional regulations.",
        server_name="regulatory_mcp",
        handler=validate_bonus_entitlement,
        parameters={"player_id": "string", "bonus_amount_usd": "number", "jurisdiction": "string"},
    )
