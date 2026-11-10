"""Multi-Agent Orchestrator State Definition."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from enterprise_assist.gateway.router import GatewayRoute
from enterprise_assist.models.query import DocumentChunk, EnterpriseQuery
from enterprise_assist.models.tenant import SecurityContext


class EnterpriseAgentState(TypedDict):
    """Execution state machine across multi-agent orchestrator lifecycle."""

    query: EnterpriseQuery
    security_context: SecurityContext
    sanitized_query_text: str
    guardrail_violations: list[str]
    is_blocked_by_guardrails: bool
    route: Optional[GatewayRoute]
    retrieved_chunks: list[DocumentChunk]
    mcp_tool_calls: list[dict[str, Any]]
    mcp_tool_results: list[dict[str, Any]]
    requires_human_approval: bool
    approval_status: str  # "NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED"
    final_answer: str
    confidence_score: float
    audit_trail: list[str]
