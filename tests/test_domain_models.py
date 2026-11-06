"""Unit tests for enterprise multi-tenant domain models and RBAC security context."""

from __future__ import annotations

import pytest

from enterprise_assist.models.tenant import (
    EnterpriseBrand,
    RegulatoryJurisdiction,
    SecurityContext,
    UserRole,
)


class TestSecurityContext:
    """Test RBAC entitlements and brand isolation."""

    def test_fanduel_caller_cannot_access_pokerstars(self) -> None:
        """Strict brand boundary denies cross-brand data access."""
        ctx = SecurityContext(
            user_id="usr-fd-101",
            brand=EnterpriseBrand.FANDUEL,
            jurisdiction=RegulatoryJurisdiction.US_NJ,
            roles=[UserRole.CUSTOMER_SUPPORT],
        )
        assert ctx.can_access_brand("FanDuel") is True
        assert ctx.can_access_brand("PokerStars") is False

    def test_enterprise_core_admin_can_access_all_brands(self) -> None:
        """Enterprise Core superusers can audit across brand boundaries."""
        admin_ctx = SecurityContext(
            user_id="usr-admin-01",
            brand=EnterpriseBrand.ENTERPRISE_CORE,
            jurisdiction=RegulatoryJurisdiction.GLOBAL,
            roles=[UserRole.OPERATIONS_ADMIN],
            clearance_level=5,
        )
        assert admin_ctx.can_access_brand("FanDuel") is True
        assert admin_ctx.can_access_brand("PokerStars") is True
        assert admin_ctx.can_access_brand("SkyBet") is True
        assert admin_ctx.has_role(UserRole.COMPLIANCE_AUDITOR) is True
