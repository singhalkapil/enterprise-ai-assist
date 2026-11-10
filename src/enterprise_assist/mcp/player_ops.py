"""Player Operations MCP Server.

Provides tools for KYC verification, wagering ledger audit, and account risk actions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from enterprise_assist.mcp.client import MCPHub


class MockPlayerDatabase:
    """Mock database simulating enterprise player account systems."""

    PLAYERS = {
        "PLY_78941": {
            "player_id": "PLY_78941",
            "name": "David Miller",
            "kyc_status": "VERIFIED",
            "vip_tier": "PLATINUM",
            "risk_flags": [],
            "balance_usd": 14250.00,
            "account_status": "ACTIVE",
            "wagers": [
                {"id": "w_101", "event": "Eagles vs Cowboys", "stake": 500.0, "status": "SETTLED_WON", "payout": 950.0},
                {"id": "w_102", "event": "Chiefs vs Bills", "stake": 300.0, "status": "SETTLED_LOST", "payout": 0.0},
            ],
        },
        "PLY_99420": {
            "player_id": "PLY_99420",
            "name": "Sarah Connor",
            "kyc_status": "SUSPENDED",
            "vip_tier": "STANDARD",
            "risk_flags": ["SUSPICIOUS_CHARGEBACK", "RAPID_LOGIN_FAILURES"],
            "balance_usd": 45.00,
            "account_status": "LOCKED",
            "wagers": [
                {"id": "w_201", "event": "Man City vs Liverpool", "stake": 1200.0, "status": "PENDING_INVESTIGATION", "payout": 0.0},
            ],
        },
    }


def get_player_kyc_status(player_id: str) -> dict[str, Any]:
    """Retrieve player KYC tier, identity verification status, and risk flags."""
    record = MockPlayerDatabase.PLAYERS.get(player_id)
    if not record:
        return {"error": f"Player ID {player_id} not found", "found": False}
    return {
        "found": True,
        "player_id": record["player_id"],
        "kyc_status": record["kyc_status"],
        "vip_tier": record["vip_tier"],
        "risk_flags": record["risk_flags"],
        "account_status": record["account_status"],
    }


def query_betting_ledger(player_id: str, limit: int = 5) -> dict[str, Any]:
    """Inspect settled and pending wagers for an authenticated player."""
    record = MockPlayerDatabase.PLAYERS.get(player_id)
    if not record:
        return {"error": f"Player ID {player_id} not found", "wagers": []}
    return {
        "player_id": player_id,
        "total_wagers": len(record["wagers"]),
        "wagers": record["wagers"][:limit],
    }


def request_account_restriction(player_id: str, restriction_type: str, reason: str) -> dict[str, Any]:
    """Apply an immediate precautionary limit or freeze on a high-risk account."""
    if player_id not in MockPlayerDatabase.PLAYERS:
        return {"success": False, "error": f"Player ID {player_id} not found"}

    return {
        "success": True,
        "player_id": player_id,
        "restriction_applied": restriction_type,
        "reason": reason,
        "status": "APPLIED_PENDING_SUPERVISORY_AUDIT",
    }


def register_player_ops_tools(hub: MCPHub) -> None:
    """Register all player ops tools to the central MCP hub."""
    hub.register_tool(
        name="get_player_kyc_status",
        description="Query player verification status, VIP tier, and fraud risk flags.",
        server_name="player_ops_mcp",
        handler=get_player_kyc_status,
        parameters={"player_id": "string"},
    )
    hub.register_tool(
        name="query_betting_ledger",
        description="Audit player wagers, stakes, settlement outcomes, and payout records.",
        server_name="player_ops_mcp",
        handler=query_betting_ledger,
        parameters={"player_id": "string", "limit": "integer"},
    )
    hub.register_tool(
        name="request_account_restriction",
        description="Enforce precautionary limits or freezes on suspicious player accounts.",
        server_name="player_ops_mcp",
        handler=request_account_restriction,
        parameters={"player_id": "string", "restriction_type": "string", "reason": "string"},
    )
