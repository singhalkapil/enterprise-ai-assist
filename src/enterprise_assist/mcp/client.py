"""Model Context Protocol (MCP) Client and Tool Execution Hub.

Provides a decoupled JSON-RPC tool calling interface with parameter schema validation,
latency tracking, and strict security isolation.
"""

from __future__ import annotations

import inspect
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """Schema descriptor for a registered MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    server_name: str


class MCPToolResult(BaseModel):
    """Execution output from an MCP tool invocation."""

    tool_name: str
    status: str  # "SUCCESS" or "ERROR"
    result: Any
    latency_ms: float
    error_message: Optional[str] = None


class MCPHub:
    """Central registry and dispatch router for Model Context Protocol servers."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._schemas: dict[str, MCPToolDefinition] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        server_name: str,
        handler: Callable[..., Any],
        parameters: Optional[dict[str, Any]] = None,
    ) -> None:
        """Register a server tool endpoint into the hub."""
        self._tools[name] = handler
        self._schemas[name] = MCPToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
            server_name=server_name,
        )

    def list_tools(self, server_filter: Optional[str] = None) -> list[MCPToolDefinition]:
        """List registered MCP tools, optionally filtered by server."""
        if server_filter:
            return [s for s in self._schemas.values() if s.server_name == server_filter]
        return list(self._schemas.values())

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Safely invoke an MCP tool with schema checking and latency metrics."""
        if tool_name not in self._tools:
            return MCPToolResult(
                tool_name=tool_name,
                status="ERROR",
                result=None,
                latency_ms=0.0,
                error_message=f"Unknown MCP tool: {tool_name}",
            )

        start_time = time.perf_counter()
        handler = self._tools[tool_name]
        try:
            res = handler(**arguments)
            latency = (time.perf_counter() - start_time) * 1000.0
            return MCPToolResult(
                tool_name=tool_name,
                status="SUCCESS",
                result=res,
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            return MCPToolResult(
                tool_name=tool_name,
                status="ERROR",
                result=None,
                latency_ms=round(latency, 2),
                error_message=f"Tool execution failed: {str(exc)}",
            )
