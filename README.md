# Store Analytics Agent — AI Engineer Portfolio

> "I built an agent that never hallucinates a number: it always pulls from the correct source. And I have an eval system that proves it and blocks the merge if the agent starts routing wrong."

## The Problem

LLM agents with tool-calling are becoming standard in production. But most teams deploy them without systematic evaluation. The result: agents that silently hallucinate numbers, route to wrong tools, or break after prompt changes — and nobody knows until a user complains.

**This project demonstrates how to build an agent with an evaluation layer that catches these failures before they reach production.**

## What It Does

A **Store Analytics Assistant** that answers questions about a fictional online store by deciding which tool to use:

| Tool | Purpose | Example |
|---|---|---|
| `query_db(sql)` | Read-only SQL on the store database | "Total revenue from completed orders" |
| `web_search(query)` | External/current info (exchange rates, etc.) | "What's the EUR/USD rate today?" |
| `calculator(expression)` | Exact arithmetic | "21% VAT on 1,240" |

The **routing is the heart of the evals** — each request has one correct tool, and catching wrong routing is the star metric.

## Architecture

```
                    ┌──────────────┐
                    │   User Query │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Agent Loop  │◄──── System Prompt
                    │  (Groq LLM)  │
                    └──┬───┬───┬──┘
                       │   │   │
            ┌──────────┘   │   └──────────┐
            ▼              ▼              ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │ query_db │   │web_search│   │calculator│
     └──────────┘   └──────────┘   └──────────┘
            │              │              │
            └──────┬───────┴──────┬───────┘
                   │              │
              ┌────▼────┐   ┌────▼────┐
              │ SQLite  │   │DuckDuck │
              │   DB    │   │  Go API │
              └─────────┘   └─────────┘
```

**Key design decision:** `run_agent()` is a pure function that returns `AgentResult` with full trajectory. Both the UI and the eval harness call the same function — no duplicate code.

## Evaluation Framework

### The Golden Dataset

**92 test cases** across 5 categories:

| Category | Count | % | Description |
|---|---|---|---|
| Routing (single tool) | 40 | 43.5% | One correct tool: DB / web / calc |
| Multi-step | 15 | 16.3% | 2+ tools in sequence (e.g., web → calc) |
| Hallucination traps | 12 | 13.0% | Questions where the agent MUST use a tool |
| Refuse / out-of-scope | 15 | 16.3% | Destructive ops, non-store questions |
| Adversarial | 10 | 10.9% | Prompt injection, social engineering |

### Metrics (8 total)

| # | Metric | Type | What It Measures |
|---|---|---|---|
| 1 | **Tool Selection Accuracy** | Deterministic | Did the agent call the expected tool(s)? |
| 2 | **Task Completion** | Deterministic + Judge | Does the answer meet acceptance criteria? |
| 3 | **Tool-Call Validity** | Deterministic | Are SQL/expressions well-formed? |
| 4 | **No-Hallucinated-Numbers** | Deterministic | Do all numbers in the answer come from tool results? |
| 5 | **Error Handling** | Deterministic | Does the agent recover gracefully from failures? |
| 6 | **Trajectory Quality** | LLM-as-Judge (Mistral) | Efficiency, reasoning, uncertainty handling (1-5) |
| 7 | **Judge Validation** | Human concordance | How well does the judge agree with human labels? |
| 8 | **Cost & Latency** | System | Tokens, tool calls, p50/p95 latency per run |

### CI Gate

On every Pull Request, GitHub Actions runs the full eval harness. **The merge is blocked if:**

- Tool selection accuracy < 85%
- Task completion rate < 80%
- Any hallucinated number detected
- Any regression case fails

```bash
# Run locally
python scripts/run_evals.py --verbose

# Gate check
python scripts/gate.py

# Demo: introduce a regression
python scripts/demo_break.py
```

## A/B Experiment Results

Comparison of two Groq-hosted models on 30 golden dataset cases:

| Metric | gpt-oss-120b | qwen3.8-27b | Winner |
|---|---|---|---|
| Tool Selection | 0.992 | 0.992 | TIE |
| Task Completion | 0.833 | **0.900** | qwen3.8-27b |
| No Hallucination | **0.533** | 0.500 | gpt-oss-120b |
| Error Handling | 1.000 | 1.000 | TIE |
| **Avg Latency** | **3,360ms** | 15,141ms | gpt-oss-120b |
| **Cases Passed %** | 83.3% | **90.0%** | qwen3.8-27b |

**Conclusion:** qwen3.8-27b resolves more cases (90% vs 83%) but is 4.5x slower. For production, gpt-oss-120b offers better cost/speed tradeoff. The quality gap concentrates on medium-difficulty cases (0.43 vs 0.57).

## Tech Stack

| Component | Choice | Why |
|---|---|---|
| LLM (agent) | Groq `openai/gpt-oss-120b` | Free tier, fast inference, tool-calling support |
| LLM (judge) | Mistral `mistral-small-latest` | Different family from agent — avoids self-preference bias |
| Database | SQLite | Zero setup, reproducible, ideal for portfolio |
| Observability | Langfuse | Free tier, trace per tool-call, dashboard |
| CI | GitHub Actions | Blocks merge on metric regression |
| Eval harness | Custom Python | Deterministic + LLM-as-judge hybrid |

## Project Structure

```
.
├── data/
│   ├── golden.json              # 92 test cases
│   ├── eval_results.json        # Latest eval run
│   ├── ab_results.json          # A/B experiment results
│   └── store.db                 # SQLite (auto-generated)
├── src/store_analytics/
│   ├── agent.py                 # Agent loop + run_agent()
│   ├── llm.py                   # LLM wrapper (Groq + Mistral)
│   ├── config.py                # Config from .env
│   ├── types.py                 # AgentResult, ToolCall, AgentMetadata
│   ├── observability.py         # Langfuse tracing
│   ├── db/                      # Schema + seed script
│   ├── tools/                   # query_db, web_search, calculator
│   └── evals/                   # Harness, metrics, judge
├── scripts/
│   ├── run_evals.py             # Run evals CLI
│   ├── gate.py                  # CI gate check
│   ├── ab_experiment.py         # A/B comparison
│   └── demo_break.py            # Demo regression detection
├── .github/workflows/evals.yml  # GitHub Actions CI
└── main.py                      # Interactive agent
```

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd store-analytics-agent
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env with your Groq API key

# 3. Run the agent
python main.py "What is the total revenue from completed orders?"

# 4. Run evals
python scripts/run_evals.py --verbose

# 5. Check gate
python scripts/gate.py
```

## Observability

With Langfuse enabled, every agent run produces a trace:

```
agent_run (query="Convert 5000 USD to EUR", latency=1923ms)
  ├── web_search(query="USD to EUR exchange rate") → OK (800ms)
  └── calculator(expression="5000/1.0850") → OK (5ms)
```

Dashboard shows: latency distribution, token usage, tool-call frequency, quality scores over time.

## What I'd Do Next

1. **Improve task completion** — fine-tune system prompt for medium-difficulty cases
2. **Add RAG** — for natural language questions that need schema understanding
3. **Streaming responses** — for better UX in the web interface
4. **Cost tracking** — per-query cost attribution using Groq pricing
