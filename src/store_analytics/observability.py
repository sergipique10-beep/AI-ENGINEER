"""Observability module — tracing with Langfuse."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator

try:
    from .config import LANGFUSE_ENABLED, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
except ImportError:
    from store_analytics.config import LANGFUSE_ENABLED, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

_tracer: Any = None


def get_tracer() -> Any:
    """Lazy-load Langfuse tracer."""
    global _tracer
    if _tracer is not None:
        return _tracer

    if not LANGFUSE_ENABLED:
        return None

    try:
        from langfuse import Langfuse
        _tracer = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        return _tracer
    except Exception:
        return None


@contextmanager
def trace_agent_run(query: str) -> Generator[dict[str, Any], None, None]:
    """
    Context manager that traces an entire agent run.

    Yields a mutable dict where callers can attach metadata.
    """
    tracer = get_tracer()
    metadata: dict[str, Any] = {"query": query}

    if tracer is None:
        # No-op: just yield metadata dict
        yield metadata
        return

    t0 = time.perf_counter()
    try:
        with tracer.trace(
            name=f"agent_run",
            input={"query": query},
            metadata=metadata,
        ) as trace:
            metadata["_trace"] = trace
            metadata["_tracer"] = tracer
            yield metadata
            trace.output = metadata.get("final_answer", "")
            trace.metadata = {k: v for k, v in metadata.items() if not k.startswith("_")}
    except Exception as e:
        metadata["error"] = str(e)
        raise
    finally:
        metadata["latency_ms"] = (time.perf_counter() - t0) * 1000


@contextmanager
def trace_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    parent_metadata: dict[str, Any],
) -> Generator[dict[str, Any], None, None]:
    """
    Context manager that traces a single tool call as a child span.

    Yields a mutable dict where callers can attach the result.
    """
    tracer = parent_metadata.get("_tracer")
    trace = parent_metadata.get("_trace")

    if tracer is None or trace is None:
        # No-op
        yield {"success": True}
        return

    t0 = time.perf_counter()
    span_metadata: dict[str, Any] = {}
    try:
        with tracer.span(
            name=f"tool:{tool_name}",
            input=arguments,
            metadata={"tool": tool_name},
            parent_trace_id=trace.id if hasattr(trace, "id") else None,
        ) as span:
            span_metadata["_span"] = span
            yield span_metadata

            result = span_metadata.get("result", "")
            success = span_metadata.get("success", True)

            span.output = result[:2000] if isinstance(result, str) else str(result)[:2000]
            span.metadata = {
                "tool": tool_name,
                "success": success,
                "latency_ms": (time.perf_counter() - t0) * 1000,
            }
    except Exception as e:
        span_metadata["success"] = False
        span_metadata["error"] = str(e)
        raise
    finally:
        span_metadata["latency_ms"] = (time.perf_counter() - t0) * 1000


def flush_traces() -> None:
    """Flush any pending traces to Langfuse."""
    tracer = get_tracer()
    if tracer:
        try:
            tracer.flush()
        except Exception:
            pass
