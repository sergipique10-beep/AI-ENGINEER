# Loom Video Script — Store Analytics Agent

**Duration:** 2-3 minutes
**Tone:** Confident, technical, concise
**Audience:** Hiring manager / tech lead

---

## Opening (0:00 - 0:20)

> "Hi, I'm [Name]. I'm going to walk you through my AI Engineer portfolio project: an LLM agent with a systematic evaluation framework that catches hallucinations and wrong tool routing before they reach production."

**Screen:** Show the README title / architecture diagram.

---

## The Problem (0:20 - 0:40)

> "Most teams deploy LLM agents without knowing if they hallucinate numbers or route to the wrong tool. My agent answers store analytics questions by choosing between a SQL database, a web search, or a calculator. The key insight: every question has ONE correct tool, so I can systematically verify the agent's routing."

**Screen:** Show the three tools and example queries.

---

## The Agent (0:40 - 1:10)

> "The agent loop is transparent — each step is recorded as a trajectory. Let me show you a real example."

**Demo:** Run `python main.py "Convert 5000 USD to EUR"`

> "Watch: it calls web_search for the exchange rate, then calculator for the conversion. Two tools, in sequence. The trajectory is recorded with every argument and result."

**Screen:** Show the terminal output with both tool calls.

---

## The Eval System (1:10 - 1:50)

> "Here's where it gets interesting. I built a golden dataset of 92 test cases across 5 categories: single-tool routing, multi-step, hallucination traps, out-of-scope, and adversarial."

**Screen:** Show the radar chart from `data/charts/radar.png`

> "Six metrics are computed per run. Tool selection accuracy checks if the agent called the right tool. No-hallucinated-numbers — the star metric — verifies every number in the answer came from a tool result, not from the LLM's imagination."

**Screen:** Show the category breakdown chart.

---

## CI Gate Demo (1:50 - 2:20)

> "Now the real test: I'm going to intentionally break the calculator and show you what happens."

**Demo:** Run `python scripts/demo_break.py`

> "I introduced a bug that divides every calculation by 2. The eval harness runs, the gate checks thresholds — and it catches the regression. In production, this would block the merge."

**Screen:** Show the gate output with FAIL status and exit code 1.

---

## A/B Results (2:20 - 2:40)

> "I also ran an A/B experiment comparing two models. qwen3.8-27b solves 90% of cases but is 4.5x slower. gpt-oss-120b solves 83% but with much better latency. For production, I'd choose the faster model — the quality gap is small and concentrated in edge cases."

**Screen:** Show the A/B comparison bar chart.

---

## Closing (2:40 - 3:00)

> "The full project — agent, 92 golden cases, 6 metrics, CI gate, observability layer — is on GitHub. Every eval run produces a results.json artifact so I can track quality over time. Thanks for watching."

**Screen:** Show the GitHub repo URL.

---

## Recording Tips

1. **Terminal font size:** 16pt minimum, dark theme
2. **Speed:** Don't rush — pauses are fine
3. **Audio:** Use a good mic, no background noise
4. **Edits:** Cut any dead time, keep it tight
5. **Show, don't tell:** Let the terminal output speak for itself
