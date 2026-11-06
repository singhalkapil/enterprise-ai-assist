"""Enterprise query and response data contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from enterprise_assist.models.tenant import SecurityContext


class DocumentChunk(BaseModel):
    """Retrieved document chunk with tenant and ACL security metadata."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    doc_id: str
    text: str
    brand: str
    jurisdiction: str
    min_clearance: int = 1
    required_roles: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0


class EnterpriseQuery(BaseModel):
    """Incoming user inquiry with security context and operational parameters."""

    model_config = ConfigDict(frozen=True)

    query_id: str
    prompt: str
    context: SecurityContext
    allow_tool_execution: bool = True
    session_id: Optional[str] = None


class AgentResponse(BaseModel):
    """Synthesized enterprise assist output with grounding citations and audit data."""

    model_config = ConfigDict(frozen=True)

    query_id: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    model_tier_used: str
    faithfulness_score: float = Field(default=0.95, ge=0.0, le=1.0)
    requires_human_approval: bool = False
    approval_token: Optional[str] = None
    audit_trace: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
