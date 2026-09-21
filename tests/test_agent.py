"""Smoke tests for the agent loop, using a fake LLM (no API keys needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from store_analytics.llm import LLMResponse


class FakeLLMClient:
    """Replays a scripted sequence of LLMResponses instead of calling a real API."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def call(self, messages, tools=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools})
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of scripted responses")
        return self._responses.pop(0)


def _tool_call_response(name: str, arguments: dict, call_id: str = "call_1") -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[{"id": call_id, "name": name, "arguments": arguments}],
        prompt_tokens=10,
        completion_tokens=5,
        model="fake-model",
        provider="fake",
        latency_ms=1.0,
    )


def _final_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=[],
        prompt_tokens=10,
        completion_tokens=5,
        model="fake-model",
        provider="fake",
        latency_ms=1.0,
    )


def test_agent_calls_tool_then_answers(monkeypatch):
    import store_analytics.agent as agent_mod

    fake = FakeLLMClient([
        _tool_call_response("calculator", {"expression": "2 + 2"}),
        _final_response("The answer is 4."),
    ])
    monkeypatch.setattr(agent_mod, "llm_client", fake)

    result = agent_mod.run_agent("What is 2 + 2?")

    assert result.final_answer == "The answer is 4."
    assert len(result.trajectory) == 1
    assert result.trajectory[0].tool_name == "calculator"
    assert result.trajectory[0].success is True
    assert len(fake.calls) == 2

    print("  agent_calls_tool_then_answers: PASSED")


def test_agent_no_tools_needed(monkeypatch):
    import store_analytics.agent as agent_mod

    fake = FakeLLMClient([_final_response("Hello, how can I help?")])
    monkeypatch.setattr(agent_mod, "llm_client", fake)

    result = agent_mod.run_agent("Hi")

    assert result.final_answer == "Hello, how can I help?"
    assert result.trajectory == []

    print("  agent_no_tools_needed: PASSED")


def test_agent_handles_unknown_tool(monkeypatch):
    import store_analytics.agent as agent_mod

    fake = FakeLLMClient([
        _tool_call_response("not_a_real_tool", {}),
        _final_response("I couldn't complete that."),
    ])
    monkeypatch.setattr(agent_mod, "llm_client", fake)

    result = agent_mod.run_agent("Do something unsupported")

    assert result.trajectory[0].success is False
    assert "Unknown tool" in result.trajectory[0].result

    print("  agent_handles_unknown_tool: PASSED")


def test_agent_respects_max_tool_calls(monkeypatch):
    import store_analytics.agent as agent_mod

    # Always requests another tool call — the loop must stop after MAX_TOOL_CALLS steps.
    responses = [_tool_call_response("calculator", {"expression": "1 + 1"}, call_id=f"c{i}")
                 for i in range(agent_mod.MAX_TOOL_CALLS)]
    fake = FakeLLMClient(responses)
    monkeypatch.setattr(agent_mod, "llm_client", fake)

    result = agent_mod.run_agent("Loop forever")

    assert len(result.trajectory) == agent_mod.MAX_TOOL_CALLS
    assert len(fake.calls) == agent_mod.MAX_TOOL_CALLS

    print("  agent_respects_max_tool_calls: PASSED")


if __name__ == "__main__":
    class _FakeMonkeypatch:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    print("Running agent smoke tests...\n")
    mp = _FakeMonkeypatch()
    test_agent_calls_tool_then_answers(mp)
    test_agent_no_tools_needed(mp)
    test_agent_handles_unknown_tool(mp)
    test_agent_respects_max_tool_calls(mp)
    print("\nAll agent tests passed!")
