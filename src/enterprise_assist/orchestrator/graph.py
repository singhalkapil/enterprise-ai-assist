"""Stateful LangGraph Multi-Agent Supervisory Orchestrator with HITL checkpoints."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from langgraph.graph import END, StateGraph

from enterprise_assist.gateway.router import EnterpriseModelGateway
from enterprise_assist.guardrails.injection_defense import InjectionDefense
from enterprise_assist.guardrails.pii_masker import PIIMasker
from enterprise_assist.guardrails.regulatory_gate import RegulatoryGatekeeper
from enterprise_assist.mcp.client import MCPHub
from enterprise_assist.mcp.player_ops import register_player_ops_tools
from enterprise_assist.mcp.regulatory_kb import register_regulatory_tools
from enterprise_assist.models.query import AgentResponse, DocumentChunk, EnterpriseQuery
from enterprise_assist.models.tenant import SecurityContext
from enterprise_assist.orchestrator.state import EnterpriseAgentState
from enterprise_assist.rag.hybrid_search import MultiTenantHybridRAG


class EnterpriseAgentOrchestrator:
    """Enterprise multi-agent supervisory orchestrator with regulatory verification and HITL."""

    def __init__(
        self,
        rag_engine: Optional[MultiTenantHybridRAG] = None,
        mcp_hub: Optional[MCPHub] = None,
    ) -> None:
        self.rag_engine = rag_engine or MultiTenantHybridRAG()
        if mcp_hub:
            self.mcp_hub = mcp_hub
        else:
            self.mcp_hub = MCPHub()
            register_player_ops_tools(self.mcp_hub)
            register_regulatory_tools(self.mcp_hub)

        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(EnterpriseAgentState)

        builder.add_node("guardrail_node", self.guardrail_node)
        builder.add_node("routing_node", self.routing_node)
        builder.add_node("retrieval_node", self.retrieval_node)
        builder.add_node("tool_node", self.tool_node)
        builder.add_node("hitl_checkpoint_node", self.hitl_checkpoint_node)
        builder.add_node("synthesis_node", self.synthesis_node)

        builder.set_entry_point("guardrail_node")

        # Guardrail conditional branch: if blocked, go straight to synthesis; otherwise continue
        builder.add_conditional_edges(
            "guardrail_node",
            lambda s: "blocked" if s["is_blocked_by_guardrails"] else "passed",
            {
                "blocked": "synthesis_node",
                "passed": "routing_node",
            },
        )

        builder.add_edge("routing_node", "retrieval_node")
        builder.add_edge("retrieval_node", "tool_node")
        builder.add_edge("tool_node", "hitl_checkpoint_node")

        # HITL conditional branch: if pending supervisory approval, pause at checkpoint
        builder.add_conditional_edges(
            "hitl_checkpoint_node",
            lambda s: "paused" if (s["requires_human_approval"] and s["approval_status"] == "PENDING") else "resume",
            {
                "paused": END,
                "resume": "synthesis_node",
            },
        )

        builder.add_edge("synthesis_node", END)

        return builder.compile()

    def guardrail_node(self, state: EnterpriseAgentState) -> dict[str, Any]:
        """Validate input prompt against injection attacks, PII leaks, and regulatory rules."""
        raw_text = state["query"].prompt
        context = state["security_context"]
        violations = []
        audit = list(state.get("audit_trail", []))

        # 1. PII Redaction
        sanitized, redactions = PIIMasker.redact(raw_text)
        if redactions:
            audit.append(f"PII Redaction: Masked {len(redactions)} sensitive token(s): {', '.join(redactions)}")

        # 2. Prompt Injection Defense
        inj_res = InjectionDefense.audit(sanitized)
        if not inj_res.is_safe:
            violations.extend(inj_res.violations)
            audit.append(f"Security Alert: Injection attempt intercepted: {', '.join(inj_res.violations)}")

        # 3. Regulatory Gate
        reg_res = RegulatoryGatekeeper.evaluate(sanitized, context)
        if not reg_res.is_compliant:
            violations.extend(reg_res.violations)
            audit.append(f"Regulatory Violation: {', '.join(reg_res.violations)}")

        is_blocked = len(violations) > 0

        return {
            "sanitized_query_text": sanitized,
            "guardrail_violations": violations,
            "is_blocked_by_guardrails": is_blocked,
            "audit_trail": audit,
        }

    def routing_node(self, state: EnterpriseAgentState) -> dict[str, Any]:
        """Resolve model gateway routing tier (SLM vs Frontier)."""
        prompt = state["sanitized_query_text"]
        audit = list(state.get("audit_trail", []))

        route = EnterpriseModelGateway.resolve_route(prompt)
        audit.append(f"Gateway Router: Routed to {route.tier} ({route.primary_model})")

        return {
            "route": route,
            "audit_trail": audit,
        }

    def retrieval_node(self, state: EnterpriseAgentState) -> dict[str, Any]:
        """Execute RBAC-scoped hybrid search over enterprise knowledge base."""
        query = state["sanitized_query_text"]
        context = state["security_context"]
        audit = list(state.get("audit_trail", []))

        chunks = self.rag_engine.search(query, context, top_k=3)
        audit.append(f"Hybrid RAG: Retrieved {len(chunks)} RBAC-authorized knowledge chunk(s)")

        return {
            "retrieved_chunks": chunks,
            "audit_trail": audit,
        }

    def tool_node(self, state: EnterpriseAgentState) -> dict[str, Any]:
        """Parse required operations and execute via Model Context Protocol (MCP) servers."""
        prompt = state["sanitized_query_text"]
        context = state["security_context"]
        audit = list(state.get("audit_trail", []))

        tool_calls = []
        tool_results = []
        requires_approval = False

        # Extract Player ID if present
        player_match = re.search(r"\b(PLY_\w+)\b", prompt, re.I)
        if player_match:
            player_id = player_match.group(1).upper()

            # Execute KYC check
            kyc_call = {"name": "get_player_kyc_status", "args": {"player_id": player_id}}
            tool_calls.append(kyc_call)
            kyc_res = self.mcp_hub.execute_tool("get_player_kyc_status", {"player_id": player_id})
            tool_results.append(kyc_res.model_dump())
            audit.append(f"MCP Hub: Executed get_player_kyc_status for {player_id} [{kyc_res.status}]")

            # Check if bonus request
            bonus_match = re.search(r"\b(?:bonus|retention|promo|credit)\b.*?\$?(\d+)", prompt, re.I)
            if bonus_match:
                amount = float(bonus_match.group(1))
                bonus_call = {
                    "name": "validate_bonus_entitlement",
                    "args": {"player_id": player_id, "bonus_amount_usd": amount, "jurisdiction": context.jurisdiction.value},
                }
                tool_calls.append(bonus_call)
                bonus_res = self.mcp_hub.execute_tool(
                    "validate_bonus_entitlement",
                    {"player_id": player_id, "bonus_amount_usd": amount, "jurisdiction": context.jurisdiction.value},
                )
                tool_results.append(bonus_res.model_dump())
                audit.append(f"MCP Hub: Executed validate_bonus_entitlement ({amount} USD) [{bonus_res.status}]")

                if bonus_res.result and bonus_res.result.get("requires_human_approval"):
                    requires_approval = True
                    audit.append("HITL Gate: Bonus exceeds threshold; flagged for Human-in-the-Loop supervisory review.")

            # Check if restriction/freeze requested
            if re.search(r"\b(freeze|suspend|lock|restrict)\b", prompt, re.I):
                restr_call = {
                    "name": "request_account_restriction",
                    "args": {"player_id": player_id, "restriction_type": "ACCOUNT_FREEZE", "reason": "Precautionary investigation"},
                }
                tool_calls.append(restr_call)
                restr_res = self.mcp_hub.execute_tool(
                    "request_account_restriction",
                    {"player_id": player_id, "restriction_type": "ACCOUNT_FREEZE", "reason": "Precautionary investigation"},
                )
                tool_results.append(restr_res.model_dump())
                requires_approval = True
                audit.append(f"HITL Gate: Account freeze action initiated on {player_id}; supervisory sign-off required.")

        return {
            "mcp_tool_calls": tool_calls,
            "mcp_tool_results": tool_results,
            "requires_human_approval": requires_approval,
            "audit_trail": audit,
        }

    def hitl_checkpoint_node(self, state: EnterpriseAgentState) -> dict[str, Any]:
        """Human-in-the-Loop decision checkpoint gate."""
        audit = list(state.get("audit_trail", []))
        approval_status = state.get("approval_status", "NOT_REQUIRED")

        if state["requires_human_approval"]:
            if approval_status == "PENDING":
                audit.append("HITL State Machine: Paused awaiting supervisor clearance.")
            elif approval_status == "APPROVED":
                audit.append("HITL State Machine: Cleared by Operations Supervisor; resuming downstream synthesis.")
            elif approval_status == "REJECTED":
                audit.append("HITL State Machine: Rejected by Operations Supervisor.")

        return {
            "approval_status": approval_status,
            "audit_trail": audit,
        }

    def synthesis_node(self, state: EnterpriseAgentState) -> dict[str, Any]:
        """Synthesize final grounded response with governance citations."""
        audit = list(state.get("audit_trail", []))

        # Case 1: Intercepted by guardrails
        if state["is_blocked_by_guardrails"]:
            violations_summary = "; ".join(state["guardrail_violations"])
            answer = (
                f"Request Declined by Enterprise Governance Policy: {violations_summary}. "
                "This action has been logged in accordance with jurisdictional compliance."
            )
            audit.append("Synthesis Node: Emitted formal governance rejection response.")
            return {
                "final_answer": answer,
                "confidence_score": 0.0,
                "audit_trail": audit,
            }

        # Case 2: Intercepted by rejected HITL
        if state["requires_human_approval"] and state["approval_status"] == "REJECTED":
            answer = "Action Rejected: Operations Supervisor declined the requested high-risk action."
            audit.append("Synthesis Node: Emitted HITL rejection response.")
            return {
                "final_answer": answer,
                "confidence_score": 0.95,
                "audit_trail": audit,
            }

        # Case 3: Successfully synthesized
        retrieved_texts = [f"[{c.doc_id}] {c.text}" for c in state["retrieved_chunks"]]
        tool_summaries = []
        for r in state["mcp_tool_results"]:
            tool_summaries.append(f"Tool {r['tool_name']}: {r['result']}")

        evidence = []
        if retrieved_texts:
            evidence.append("Knowledge References:\n" + "\n".join(retrieved_texts))
        if tool_summaries:
            evidence.append("Live Telemetry:\n" + "\n".join(tool_summaries))

        evidence_block = "\n\n".join(evidence) if evidence else "No auxiliary domain chunks required."
        model_name = state["route"].primary_model if state["route"] else "default-model"

        final_answer = (
            f"Response synthesized under brand [{state['security_context'].brand.value}] "
            f"jurisdiction [{state['security_context'].jurisdiction.value}] via {model_name}.\n\n"
            f"{evidence_block}"
        )
        audit.append("Synthesis Node: Successfully generated grounded agent answer.")

        return {
            "final_answer": final_answer,
            "confidence_score": 0.96,
            "audit_trail": audit,
        }

    def process_query(
        self,
        query: EnterpriseQuery,
        supervisor_approval: Optional[str] = None,
    ) -> AgentResponse:
        """Execute end-to-end multi-agent orchestration pipeline."""
        initial_state: EnterpriseAgentState = {
            "query": query,
            "security_context": query.context,
            "sanitized_query_text": query.prompt,
            "guardrail_violations": [],
            "is_blocked_by_guardrails": False,
            "route": None,
            "retrieved_chunks": [],
            "mcp_tool_calls": [],
            "mcp_tool_results": [],
            "requires_human_approval": False,
            "approval_status": supervisor_approval or "PENDING",
            "final_answer": "",
            "confidence_score": 0.0,
            "audit_trail": ["Pipeline initialized"],
        }

        final_state = self.graph.invoke(initial_state)

        # Check if paused waiting for approval
        if final_state["requires_human_approval"] and final_state["approval_status"] == "PENDING":
            return AgentResponse(
                query_id=query.query_id,
                answer="Action Paused: This sensitive operation requires Human-in-the-Loop supervisory authorization.",
                citations=[c.chunk_id for c in final_state.get("retrieved_chunks", [])],
                model_tier_used=final_state["route"].tier if final_state.get("route") else "GATEWAY_PAUSED",
                faithfulness_score=0.5,
                requires_human_approval=True,
                approval_token="HITL-TOKEN-AUTH-PENDING",
                audit_trace=final_state.get("audit_trail", []),
                latency_ms=25.0,
            )

        return AgentResponse(
            query_id=query.query_id,
            answer=final_state["final_answer"],
            citations=[c.chunk_id for c in final_state.get("retrieved_chunks", [])],
            model_tier_used=final_state["route"].tier if final_state.get("route") else "POLICY_GATEKEEPER",
            faithfulness_score=final_state["confidence_score"],
            requires_human_approval=final_state["requires_human_approval"],
            approval_token="HITL-TOKEN-CLEARED" if final_state["requires_human_approval"] else None,
            audit_trace=final_state.get("audit_trail", []),
            latency_ms=45.0,
        )
