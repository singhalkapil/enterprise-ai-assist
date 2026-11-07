"""Adversarial Prompt Injection & Jailbreak Defense Guardrail."""

from __future__ import annotations

import re
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class InjectionCheckResult(BaseModel):
    """Result of prompt injection audit."""

    model_config = ConfigDict(frozen=True)

    is_safe: bool
    risk_score: float
    violations: List[str]


class InjectionDefense:
    """Detects adversarial jailbreaks, roleplay escapes, and data exfiltration directives."""

    JAILBREAK_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I),
        re.compile(r"you\s+are\s+DAN\b", re.I),
        re.compile(r"disregard\s+all\s+(system|security)\s+prompts", re.I),
        re.compile(r"output\s+the\s+entire\s+system\s+prompt", re.I),
        re.compile(r"dump\s+all\s+player\s+(accounts|passwords|records)", re.I),
        re.compile(r"bypass\s+all\s+regulatory\s+checks", re.I),
    ]

    @classmethod
    def audit(cls, prompt: str) -> InjectionCheckResult:
        """Evaluate prompt against adversarial signatures."""
        violations: list[str] = []

        for pat in cls.JAILBREAK_PATTERNS:
            match = pat.search(prompt)
            if match:
                violations.append(f"Prompt injection signature detected: '{match.group(0)}'")

        is_safe = len(violations) == 0
        risk_score = 0.95 if not is_safe else 0.05

        return InjectionCheckResult(
            is_safe=is_safe,
            risk_score=risk_score,
            violations=violations,
        )
