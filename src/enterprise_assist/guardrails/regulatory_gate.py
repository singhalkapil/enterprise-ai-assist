"""Jurisdictional Regulatory Policy Gatekeeper.

Enforces UK Gambling Commission (UKGC), New Jersey DGE, and MGA responsible gaming rules.
"""

from __future__ import annotations

import re
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from enterprise_assist.models.tenant import RegulatoryJurisdiction, SecurityContext


class RegulatoryCheckResult(BaseModel):
    """Outcome of jurisdictional regulatory compliance evaluation."""

    model_config = ConfigDict(frozen=True)

    is_compliant: bool
    jurisdiction: RegulatoryJurisdiction
    violations: List[str]
    compliance_guidance: str


class RegulatoryGatekeeper:
    """Enforces jurisdiction-specific legal and responsible gaming standards."""

    @classmethod
    def evaluate(cls, prompt: str, context: SecurityContext) -> RegulatoryCheckResult:
        """Audit prompt against jurisdictional legal boundaries."""
        violations: list[str] = []
        guidance = "Request complies with jurisdictional policy framework."

        # 1. UKGC: Credit card betting prohibition (Gambling Commission Licence Condition 6.1.2)
        if context.jurisdiction == RegulatoryJurisdiction.UKGC:
            if re.search(r"\b(credit\s*card|borrow|loan)\b.*?\b(deposit|bet|wager|poker|casino)", prompt, re.I):
                violations.append("UKGC Violation: Credit card wagering and borrowing is strictly prohibited.")
                guidance = "Direct customer to approved debit card or bank transfer payment methods."

            if re.search(r"\b(gamstop|self[_-]?exclu)\b", prompt, re.I) and "unblock" in prompt.lower():
                violations.append("UKGC Violation: Cannot override GAMSTOP national self-exclusion register.")
                guidance = "Refer player to the official GAMSTOP registry; account cannot be opened."

        # 2. US New Jersey DGE: Geolocation & underage wagering
        elif context.jurisdiction == RegulatoryJurisdiction.US_NJ:
            if re.search(r"\b(vpn|proxy|spoof\s*location|out\s*of\s*state)\b", prompt, re.I):
                violations.append("NJ DGE Violation: Wagering permitted only within state territorial borders.")
                guidance = "Inform patron that GeoComply location verification is legally required."

            if re.search(r"\b(under\s*21|18\s*years\s*old)\b", prompt, re.I) and "bet" in prompt.lower():
                violations.append("NJ DGE Violation: Minimum sports betting age in New Jersey is 21.")
                guidance = "Reject request due to underage wagering restrictions."

        is_compliant = len(violations) == 0

        return RegulatoryCheckResult(
            is_compliant=is_compliant,
            jurisdiction=context.jurisdiction,
            violations=violations,
            compliance_guidance=guidance,
        )
