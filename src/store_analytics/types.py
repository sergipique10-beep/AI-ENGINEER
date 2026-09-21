"""Core types for the agent system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation in the agent trajectory."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    success: bool
    latency_ms: float = 0.0


@dataclass
class AgentResult:
    """Complete result from an agent run, including full trajectory."""

    final_answer: str
    trajectory: list[ToolCall] = field(default_factory=list)
    metadata: AgentMetadata = field(default_factory=lambda: AgentMetadata())
    error: str | None = None


@dataclass
class AgentMetadata:
    """Metrics collected during a single agent run."""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    num_tool_calls: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    model_used: str = ""
    provider_used: str = ""


@dataclass
class ToolDefinition:
    """Schema for a tool that the agent can call."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    function: Any  # callable
