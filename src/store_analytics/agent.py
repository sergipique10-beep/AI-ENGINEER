"""Agent loop — the core of the Store Analytics Assistant."""

from __future__ import annotations

import json
import time
from typing import Any

from .config import MAX_TOOL_CALLS
from .llm import llm_client, LLMResponse
from .tools import ALL_TOOLS, ALL_TOOL_FUNCTIONS
from .types import AgentMetadata, AgentResult, ToolCall
from .observability import trace_agent_run, trace_tool_call, flush_traces

SYSTEM_PROMPT = """You are a Store Analytics Assistant. You help users answer questions about an online store.

You have access to these tools:
1. query_db(sql) — Run read-only SQL queries on the store database. Use this for any question about sales, revenue, customers, products, or order data.
2. web_search(query) — Search the web for current/external information (exchange rates, market data, etc.). Do NOT use this for store data.
3. calculator(expression) — Evaluate mathematical expressions precisely. Use this for any arithmetic.

RULES:
- ALWAYS use the appropriate tool(s) to get real data. NEVER make up numbers.
- For store data, use query_db. For external/current data, use web_search. For math, use calculator.
- If a query requires multiple steps (e.g., get exchange rate then convert), call tools in sequence.
- After getting tool results, synthesize them into a clear final answer.
- If you cannot answer with tools, say so honestly.
"""


def _build_tools_for_llm() -> list[dict[str, Any]]:
    """Convert ToolDefinition schemas to the format expected by LLM APIs."""
    return ALL_TOOLS


def _execute_tool(tool_name: str, arguments: dict[str, Any]) -> tuple[str, bool, float]:
    """Execute a tool and return (result, success, latency_ms)."""
    func = ALL_TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"}), False, 0.0

    t0 = time.perf_counter()
    try:
        result = func(**arguments)
        latency_ms = (time.perf_counter() - t0) * 1000
        return result, True, latency_ms
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return json.dumps({"error": f"Tool execution failed: {e}"}), False, latency_ms


def run_agent(query: str, *, verbose: bool = False) -> AgentResult:
    """
    Run the agent on a user query and return the full result with trajectory.

    This is the single entry point for both the UI and the eval harness.
    """
    t_start = time.perf_counter()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    trajectory: list[ToolCall] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    model_used = ""

    with trace_agent_run(query) as agent_meta:
        for step in range(MAX_TOOL_CALLS):
            # Call LLM
            try:
                response: LLMResponse = llm_client.call(
                    messages=messages,
                    tools=_build_tools_for_llm(),
                    provider="groq",
                )
            except Exception as e:
                total_latency_ms = (time.perf_counter() - t_start) * 1000
                metadata = AgentMetadata(
                    total_tokens=total_prompt_tokens + total_completion_tokens,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    num_tool_calls=len(trajectory),
                    latency_ms=total_latency_ms,
                    model_used=model_used,
                    provider_used="groq",
                )
                flush_traces()
                return AgentResult(
                    final_answer="",
                    trajectory=trajectory,
                    metadata=metadata,
                    error=f"LLM call failed: {e}",
                )
            model_used = response.model
            total_prompt_tokens += response.prompt_tokens
            total_completion_tokens += response.completion_tokens

            if verbose:
                content_preview = '(none)' if not response.content else response.content[:80].encode('ascii', 'replace').decode()
                print(f"  [Step {step + 1}] Provider={response.provider}, "
                      f"Model={response.model}, "
                      f"Tool calls={len(response.tool_calls)}, "
                      f"Content={content_preview}...")

            # If no tool calls, we have a final answer
            if not response.tool_calls:
                break

            # Execute each tool call
            tool_messages = []
            for tc in response.tool_calls:
                tool_name = tc["name"]
                arguments = tc["arguments"]

                with trace_tool_call(tool_name, arguments, agent_meta) as tool_meta:
                    result_str, success, latency_ms = _execute_tool(tool_name, arguments)
                    tool_meta["result"] = result_str
                    tool_meta["success"] = success

                trajectory.append(ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result_str,
                    success=success,
                    latency_ms=latency_ms,
                ))

                if verbose:
                    status = 'OK' if success else 'FAIL'
                    print(f"    -> {tool_name}({arguments}) => {status} ({latency_ms:.0f}ms)")

                # Add tool result to messages for next LLM call
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

            # Append assistant message (with tool calls) then tool results
            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                    }
                    for tc in response.tool_calls
                ],
            })
            messages.extend(tool_messages)

        total_latency_ms = (time.perf_counter() - t_start) * 1000

        # Build metadata
        metadata = AgentMetadata(
            total_tokens=total_prompt_tokens + total_completion_tokens,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            num_tool_calls=len(trajectory),
            latency_ms=total_latency_ms,
            model_used=model_used,
            provider_used="groq",
        )

        # Extract final answer
        final_answer = ""
        if messages and messages[-1].get("role") == "assistant":
            final_answer = messages[-1].get("content", "")
        elif response.content:
            final_answer = response.content

        agent_meta["final_answer"] = final_answer
        agent_meta["num_tool_calls"] = len(trajectory)
        agent_meta["total_tokens"] = metadata.total_tokens

    # Flush traces asynchronously
    flush_traces()

    return AgentResult(
        final_answer=final_answer,
        trajectory=trajectory,
        metadata=metadata,
    )
