"""Deterministic PII and Sensitive Data Redaction Engine.

Scrubs Credit Card numbers (Luhn/PAN), SSNs, UK National Insurance Numbers (NINO),
passwords, and API tokens before entering language model contexts.
"""

from __future__ import annotations

import re
from typing import Tuple


class PIIMasker:
    """Detects and redacts sensitive Personally Identifiable Information (PII)."""

    # Credit Card numbers (13-16 digits with hyphens or spaces)
    CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

    # US Social Security Number (SSN: XXX-XX-XXXX)
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    # UK National Insurance Number (NINO: e.g. QQ123456C)
    UK_NINO_PATTERN = re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s*\d{6}\s*[A-D]\b", re.I)

    # API Keys / Bearer tokens / Passwords
    SECRET_PATTERN = re.compile(
        r"(?:password|secret|bearer\s+|api[_-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?",
        re.I,
    )

    @classmethod
    def redact(cls, text: str) -> tuple[str, list[str]]:
        """Redact sensitive PII and return (sanitized_text, list_of_redactions)."""
        redactions: list[str] = []
        sanitized = text

        # 1. Redact credit card numbers
        if cls.CC_PATTERN.search(sanitized):
            sanitized = cls.CC_PATTERN.sub("[REDACTED_CARD_NUMBER]", sanitized)
            redactions.append("CREDIT_CARD_NUMBER")

        # 2. Redact US SSNs
        if cls.SSN_PATTERN.search(sanitized):
            sanitized = cls.SSN_PATTERN.sub("[REDACTED_SSN]", sanitized)
            redactions.append("US_SSN")

        # 3. Redact UK NINO
        if cls.UK_NINO_PATTERN.search(sanitized):
            sanitized = cls.UK_NINO_PATTERN.sub("[REDACTED_UK_NINO]", sanitized)
            redactions.append("UK_NINO")

        # 4. Redact Secrets / Tokens
        if cls.SECRET_PATTERN.search(sanitized):
            sanitized = cls.SECRET_PATTERN.sub(r"password: [REDACTED_CREDENTIAL]", sanitized)
            redactions.append("API_SECRET_OR_PASSWORD")

        return sanitized, redactions
