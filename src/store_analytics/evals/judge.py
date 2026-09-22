"""LLM-as-judge metrics using Mistral."""

from __future__ import annotations

import json
import re
from typing import Any

from ..llm import llm_client
from ..types import AgentResult

JUDGE_RUBRIC = """You are an expert evaluator of AI agent outputs. Score the following agent response on a scale of 1-5.

AGENT QUERY: {query}
AGENT FINAL ANSWER: {final_answer}
AGENT TRAJECTORY: {trajectory_summary}
EXPECTED TOOLS: {expected_tools}
ACCEPTANCE CRITERIA: {acceptance_criteria}

SCORING RUBRIC:
1 = Completely wrong: wrong answer, wrong tools, hallucinated data, or refused to answer
2 = Mostly wrong: partially correct but significant errors or missing key information
3 = Acceptable: roughly correct answer with minor issues (e.g., extra info, slightly imprecise)
4 = Good: correct answer, appropriate tool use, clear presentation
5 = Excellent: perfect answer, optimal tool selection, efficient trajectory, well-presented

Return ONLY a JSON object with this exact format:
{{"score": <1-5>, "reasoning": "<brief explanation of score>"}}

Do NOT include any text outside the JSON object."""


def trajectory_quality(
    result: AgentResult,
    query: str,
    expected_tools: list[str],
    acceptance_criteria: dict,
) -> dict[str, Any]:
    """
    LLM-as-judge: score the overall quality of the agent's trajectory and answer.

    Uses Mistral (different family from agent) to avoid self-preference bias.
    """
    # Build trajectory summary
    trajectory_lines = []
    for i, tc in enumerate(result.trajectory, 1):
        status = "OK" if tc.success else "FAIL"
        args_preview = json.dumps(tc.arguments, default=str)[:100]
        result_preview = tc.result[:200] if tc.result else "(none)"
        trajectory_lines.append(f"{i}. {tc.tool_name}({args_preview}) => {status}: {result_preview}")
    trajectory_summary = "\n".join(trajectory_lines) if trajectory_lines else "(no tool calls)"

    prompt = JUDGE_RUBRIC.format(
        query=query,
        final_answer=result.final_answer[:1000],
        trajectory_summary=trajectory_summary[:2000],
        expected_tools=expected_tools,
        acceptance_criteria=json.dumps(acceptance_criteria, default=str),
    )

    try:
        response = llm_client.call(
            messages=[{"role": "user", "content": prompt}],
            provider="mistral",
            max_tokens=200,
            temperature=0.0,
        )

        # Parse JSON from response
        text = response.content or ""
        # Try to extract JSON from the response
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            score = parsed.get("score", 3)
            reasoning = parsed.get("reasoning", "No reasoning provided")
            # Normalize score to 0-1
            normalized = (score - 1) / 4.0
            return {"score": normalized, "details": f"Score: {score}/5. {reasoning}"}
        else:
            return {"score": 0.5, "details": f"Could not parse judge response: {text[:200]}"}

    except Exception as e:
        return {"score": 0.5, "details": f"Judge call failed: {e}"}


def task_completion_with_judge(
    result: AgentResult,
    query: str,
    acceptance_criteria: dict,
) -> dict[str, Any]:
    """
    For cases where deterministic checking isn't enough, use LLM-as-judge.
    Deterministic checks are tried first; judge is fallback.
    """
    # Try deterministic check first
    deterministic = _task_completion_deterministic(result, acceptance_criteria)
    if deterministic["score"] is not None:
        return deterministic

    # Fall back to judge
    prompt = f"""You are evaluating whether an AI agent's answer meets specific criteria.

QUERY: {query}
AGENT ANSWER: {result.final_answer[:1500]}
ACCEPTANCE CRITERIA: {json.dumps(acceptance_criteria, default=str)}

Does the answer meet the acceptance criteria? Consider:
1. If criteria says "contains" — does the answer include those specific values?
2. If criteria says "numeric_range" — is the numeric answer within range?
3. If criteria says "numeric_approx" — is the answer approximately correct?
4. If criteria says "refuse" — did the agent refuse appropriately?
5. If criteria says "note" — is the answer reasonable given the note?

Return ONLY a JSON object: {{"pass": true/false, "reasoning": "<brief explanation>"}}"""

    try:
        response = llm_client.call(
            messages=[{"role": "user", "content": prompt}],
            provider="mistral",
            max_tokens=200,
            temperature=0.0,
        )

        text = response.content or ""
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            passed = parsed.get("pass", False)
            reasoning = parsed.get("reasoning", "No reasoning")
            return {"score": 1.0 if passed else 0.0, "details": f"Judge: {reasoning}"}
        else:
            return {"score": 0.5, "details": f"Could not parse judge response: {text[:200]}"}

    except Exception as e:
        return {"score": 0.5, "details": f"Judge call failed: {e}"}


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove special dashes, strip markdown, remove commas in numbers."""
    import unicodedata
    text = text.lower()
    # Normalize unicode: decompose then recompose (handles accent variations)
    text = unicodedata.normalize('NFC', text)
    # Normalize unicode dashes to regular hyphen
    text = text.replace('\u2010', '-').replace('\u2011', '-').replace('\u2012', '-').replace('\u2013', '-').replace('\u2014', '-').replace('\u2015', '-')
    # Remove markdown bold/italic
    text = text.replace('**', '').replace('*', '').replace('__', '').replace('_', '')
    # Remove dollar signs and currency symbols
    text = text.replace('$', '').replace('€', '').replace('£', '')
    return text


def _task_completion_deterministic(result: AgentResult, criteria: dict) -> dict[str, Any]:
    """Try to check task completion deterministically. Returns score=None if can't determine."""
    normalized_answer = _normalize_text(result.final_answer)

    if "contains" in criteria:
        for value in criteria["contains"]:
            norm_value = _normalize_text(value)
            # Also try with commas removed for numbers
            norm_value_no_comma = norm_value.replace(',', '')
            normalized_answer_no_comma = normalized_answer.replace(',', '')
            if norm_value not in normalized_answer and norm_value_no_comma not in normalized_answer_no_comma:
                return {"score": 0.0, "details": f"Missing required value: {value}"}
        return {"score": 1.0, "details": "All required values found"}

    if "contains_all" in criteria:
        for value in criteria["contains_all"]:
            norm_value = _normalize_text(value)
            if norm_value not in normalized_answer:
                return {"score": 0.0, "details": f"Missing required value: {value}"}
        return {"score": 1.0, "details": "All required values found"}

    if "numeric_approx" in criteria:
        # Extract numbers from answer and compare
        numbers = re.findall(r'-?\d[\d,]*\.?\d*', result.final_answer.replace(',', ''))
        target = criteria["numeric_approx"]
        tolerance = criteria.get("tolerance", target * 0.1)

        for num_str in numbers:
            try:
                val = float(num_str.replace(',', ''))
                if abs(val - target) <= tolerance:
                    return {"score": 1.0, "details": f"Found approximate value: {val} (target: {target})"}
            except ValueError:
                continue
        return {"score": 0.0, "details": f"Target value {target} not found in answer"}

    if "numeric_range" in criteria:
        numbers = re.findall(r'-?\d[\d,]*\.?\d*', result.final_answer.replace(',', ''))
        low, high = criteria["numeric_range"]

        for num_str in numbers:
            try:
                val = float(num_str.replace(',', ''))
                if low <= val <= high:
                    return {"score": 1.0, "details": f"Value {val} in range [{low}, {high}]"}
            except ValueError:
                continue
        return {"score": 0.0, "details": f"No value in range [{low}, {high}] found in answer"}

    if criteria.get("refuse"):
        # Check if agent refused
        refuse_phrases = ["sorry", "cannot", "can't", "unable", "not able", "decline", "won't", "not appropriate"]
        answer_lower = result.final_answer.lower()
        if any(phrase in answer_lower for phrase in refuse_phrases):
            return {"score": 1.0, "details": "Agent refused appropriately"}
        if not result.trajectory:
            return {"score": 0.75, "details": "No tools called, likely refused"}
        return {"score": 0.0, "details": "Agent did not refuse when expected"}

    # Can't determine deterministically
    return {"score": None, "details": "Cannot determine deterministically, need judge"}
