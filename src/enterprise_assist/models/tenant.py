"""Multi-tenant RBAC and jurisdictional regulatory domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import List, Set
from pydantic import BaseModel, ConfigDict, Field


class EnterpriseBrand(StrEnum):
    """Regulated enterprise business brands / divisions."""

    FANDUEL = "FanDuel"
    POKERSTARS = "PokerStars"
    SKYBET = "SkyBet"
    ENTERPRISE_CORE = "EnterpriseCore"


class RegulatoryJurisdiction(StrEnum):
    """Licensing and regulatory compliance jurisdictions."""

    UKGC = "UKGC"          # UK Gambling Commission
    US_NJ = "US_NJ"        # New Jersey Division of Gaming Enforcement (DGE)
    MGA = "MGA"            # Malta Gaming Authority
    GLOBAL = "GLOBAL"      # Universal enterprise policies


class UserRole(StrEnum):
    """Role-Based Access Control (RBAC) operational roles."""

    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    COMPLIANCE_AUDITOR = "COMPLIANCE_AUDITOR"
    FRAUD_RISK_ANALYST = "FRAUD_RISK_ANALYST"
    OPERATIONS_ADMIN = "OPERATIONS_ADMIN"


class SecurityContext(BaseModel):
    """Authenticated caller identity with tenant and RBAC entitlements."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    brand: EnterpriseBrand
    jurisdiction: RegulatoryJurisdiction
    roles: List[UserRole] = Field(default_factory=lambda: [UserRole.CUSTOMER_SUPPORT])
    clearance_level: int = Field(default=1, ge=1, le=5)

    def can_access_brand(self, target_brand: str) -> bool:
        """Enforce strict brand data boundary isolation."""
        if self.brand == EnterpriseBrand.ENTERPRISE_CORE:
            return True
        return self.brand.value.lower() == target_brand.lower()

    def has_role(self, required_role: UserRole) -> bool:
        """Verify role presence."""
        return required_role in self.roles or UserRole.OPERATIONS_ADMIN in self.roles
