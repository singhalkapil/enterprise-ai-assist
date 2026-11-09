"""Unit tests for Model Context Protocol (MCP) Hub and Servers."""

import pytest
from enterprise_assist.mcp.client import MCPHub
from enterprise_assist.mcp.player_ops import (
    MockPlayerDatabase,
    get_player_kyc_status,
    query_betting_ledger,
    register_player_ops_tools,
    request_account_restriction,
)
from enterprise_assist.mcp.regulatory_kb import (
    check_jurisdiction_exclusion,
    register_regulatory_tools,
    validate_bonus_entitlement,
)


@pytest.fixture
def mcp_hub():
    hub = MCPHub()
    register_player_ops_tools(hub)
    register_regulatory_tools(hub)
    return hub


def test_mcp_tool_registration_and_listing(mcp_hub):
    tools = mcp_hub.list_tools()
    tool_names = {t.name for t in tools}
    assert "get_player_kyc_status" in tool_names
    assert "query_betting_ledger" in tool_names
    assert "check_jurisdiction_exclusion" in tool_names
    assert "validate_bonus_entitlement" in tool_names

    player_tools = mcp_hub.list_tools(server_filter="player_ops_mcp")
    assert len(player_tools) == 3


def test_mcp_player_kyc_tool_execution(mcp_hub):
    result = mcp_hub.execute_tool("get_player_kyc_status", {"player_id": "PLY_78941"})
    assert result.status == "SUCCESS"
    assert result.result["found"] is True
    assert result.result["kyc_status"] == "VERIFIED"
    assert result.result["vip_tier"] == "PLATINUM"
    assert result.latency_ms >= 0.0


def test_mcp_unknown_tool_handling(mcp_hub):
    result = mcp_hub.execute_tool("non_existent_tool", {})
    assert result.status == "ERROR"
    assert "Unknown MCP tool" in result.error_message


def test_mcp_regulatory_exclusion_and_bonus_caps(mcp_hub):
    # Excluded player check
    res_excl = mcp_hub.execute_tool(
        "check_jurisdiction_exclusion",
        {"player_id": "PLY_EXCLUDED_UK", "jurisdiction": "UKGC"},
    )
    assert res_excl.status == "SUCCESS"
    assert res_excl.result["is_excluded"] is True
    assert res_excl.result["registry"] == "GAMSTOP"

    # UKGC bonus caps check (> $500 requires human approval)
    res_bonus_uk = mcp_hub.execute_tool(
        "validate_bonus_entitlement",
        {"player_id": "PLY_78941", "bonus_amount_usd": 750.0, "jurisdiction": "UKGC"},
    )
    assert res_bonus_uk.result["eligible"] is False
    assert res_bonus_uk.result["requires_human_approval"] is True

    # US_NJ bonus caps ($600 is permitted without approval, > $1,000 requires approval)
    res_bonus_nj = mcp_hub.execute_tool(
        "validate_bonus_entitlement",
        {"player_id": "PLY_78941", "bonus_amount_usd": 600.0, "jurisdiction": "US_NJ"},
    )
    assert res_bonus_nj.result["eligible"] is True
    assert res_bonus_nj.result["requires_human_approval"] is False
