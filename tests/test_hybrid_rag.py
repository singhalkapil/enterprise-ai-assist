"""Unit tests for Gateway Router and Multi-Tenant Hybrid RAG Engine."""

import pytest
from enterprise_assist.gateway.router import EnterpriseModelGateway
from enterprise_assist.models.query import DocumentChunk
from enterprise_assist.models.tenant import EnterpriseBrand, RegulatoryJurisdiction, SecurityContext, UserRole
from enterprise_assist.rag.hybrid_search import MultiTenantHybridRAG


def test_gateway_router_intent_classification():
    # Simple query routes to Tier 1 SLM
    route_simple = EnterpriseModelGateway.resolve_route("What are the VIP loyalty points tiers?")
    assert route_simple.tier == "TIER_1_SLM"
    assert "llama3-2-3b" in route_simple.primary_model
    assert route_simple.max_tokens == 1024

    # Complex audit/compliance query routes to Tier 2 Frontier
    route_complex = EnterpriseModelGateway.resolve_route("Please investigate suspicious chargeback disputes for compliance audit")
    assert route_complex.tier == "TIER_2_FRONTIER"
    assert "claude-3-5-sonnet" in route_complex.primary_model
    assert route_complex.max_tokens == 4096


def test_hybrid_rag_multi_tenant_brand_isolation():
    rag = MultiTenantHybridRAG()

    docs = [
        DocumentChunk(
            chunk_id="chunk_fanduel_1",
            doc_id="fd_terms",
            text="FanDuel Sportsbook Super Bowl promotions and odds boosts rules.",
            brand=EnterpriseBrand.FANDUEL,
            jurisdiction=RegulatoryJurisdiction.US_NJ,
            min_clearance=1,
        ),
        DocumentChunk(
            chunk_id="chunk_pokerstars_1",
            doc_id="ps_tourney",
            text="PokerStars European Poker Tour qualification buy-in schedule.",
            brand=EnterpriseBrand.POKERSTARS,
            jurisdiction=RegulatoryJurisdiction.MGA,
            min_clearance=1,
        ),
        DocumentChunk(
            chunk_id="chunk_core_1",
            doc_id="core_policy",
            text="Flutter Group global AML and customer authentication standard operating procedure.",
            brand=EnterpriseBrand.ENTERPRISE_CORE,
            jurisdiction=RegulatoryJurisdiction.GLOBAL,
            min_clearance=1,
        ),
    ]
    rag.index_documents(docs)

    # Context 1: Single brand FanDuel agent
    fd_context = SecurityContext(
        user_id="usr_101",
        brand=EnterpriseBrand.FANDUEL,
        jurisdiction=RegulatoryJurisdiction.US_NJ,
        clearance_level=1,
        roles=[UserRole.CUSTOMER_SUPPORT],
    )
    results = rag.search("promotions and rules", fd_context)
    result_ids = [r.chunk_id for r in results]

    # Should see FanDuel and Core chunks, but NOT PokerStars
    assert "chunk_fanduel_1" in result_ids
    assert "chunk_pokerstars_1" not in result_ids

    # Context 2: SkyBet agent
    sky_context = SecurityContext(
        user_id="usr_102",
        brand=EnterpriseBrand.SKYBET,
        jurisdiction=RegulatoryJurisdiction.UKGC,
        clearance_level=1,
        roles=[UserRole.CUSTOMER_SUPPORT],
    )
    results_sky = rag.search("poker tournament promotions", sky_context)
    # SkyBet agent cannot see FanDuel or PokerStars
    for r in results_sky:
        assert r.brand in (EnterpriseBrand.SKYBET, EnterpriseBrand.ENTERPRISE_CORE)


def test_hybrid_rag_clearance_and_role_filtering():
    rag = MultiTenantHybridRAG()

    confidential_chunk = DocumentChunk(
        chunk_id="chunk_audit_secret",
        doc_id="secret_1",
        text="Internal fraud investigation procedures and high-roller account freezes.",
        brand=EnterpriseBrand.FANDUEL,
        jurisdiction=RegulatoryJurisdiction.US_NJ,
        min_clearance=3,
        required_roles=["COMPLIANCE_AUDITOR"],
    )
    rag.index_documents([confidential_chunk])

    # Support Agent with clearance 1 lacks access
    agent_context = SecurityContext(
        user_id="usr_201",
        brand=EnterpriseBrand.FANDUEL,
        jurisdiction=RegulatoryJurisdiction.US_NJ,
        clearance_level=1,
        roles=[UserRole.CUSTOMER_SUPPORT],
    )
    assert len(rag.search("fraud investigation", agent_context)) == 0

    # Compliance auditor with clearance 3 has access
    compliance_context = SecurityContext(
        user_id="usr_202",
        brand=EnterpriseBrand.FANDUEL,
        jurisdiction=RegulatoryJurisdiction.US_NJ,
        clearance_level=3,
        roles=[UserRole.COMPLIANCE_AUDITOR],
    )
    results = rag.search("fraud investigation", compliance_context)
    assert len(results) == 1
    assert results[0].chunk_id == "chunk_audit_secret"
