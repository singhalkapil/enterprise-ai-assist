"""Enterprise Model Gateway & Smart Cascade Router.

Provides model fallbacks, latency budgets, and cost optimization routing between
SLM (Tier 1) and Frontier (Tier 2) foundation models.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class GatewayRoute(BaseModel):
    """Model dispatch routing instructions."""

    model_config = ConfigDict(frozen=True)

    tier: str
    primary_model: str
    fallback_model: str
    max_tokens: int
    temperature: float
    timeout_seconds: float
    estimated_cost_usd_per_1k: float


class EnterpriseModelGateway:
    """Manages model selection, circuit breakers, and latency budgets."""

    # Models
    TIER_1_MODEL = "bedrock/meta.llama3-2-3b-instruct-v1:0"
    TIER_1_FALLBACK = "gemini-1.5-flash"
    TIER_2_MODEL = "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
    TIER_2_FALLBACK = "gemini-1.5-pro"

    COMPLEX_INTENTS = [
        re.compile(r"\b(audit|investigat|compliance|reconcil|dispute|legal|cross-table)\b", re.I),
        re.compile(r"\b(suspicious|aml|fraud|chargeback|sanction|pep)\b", re.I),
    ]

    @classmethod
    def resolve_route(cls, prompt: str, requires_deep_reasoning: bool = False) -> GatewayRoute:
        """Select primary and fallback models based on intent complexity."""
        is_complex = requires_deep_reasoning or any(pat.search(prompt) for pat in cls.COMPLEX_INTENTS)

        if is_complex:
            return GatewayRoute(
                tier="TIER_2_FRONTIER",
                primary_model=cls.TIER_2_MODEL,
                fallback_model=cls.TIER_2_FALLBACK,
                max_tokens=4096,
                temperature=0.1,
                timeout_seconds=25.0,
                estimated_cost_usd_per_1k=0.003,
            )

        return GatewayRoute(
            tier="TIER_1_SLM",
            primary_model=cls.TIER_1_MODEL,
            fallback_model=cls.TIER_1_FALLBACK,
            max_tokens=1024,
            temperature=0.0,
            timeout_seconds=5.0,
            estimated_cost_usd_per_1k=0.00015,
        )
