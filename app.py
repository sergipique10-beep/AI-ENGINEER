"""Streamlit app — agent demo, evals dashboard, and observability.

Single deployable entry point for the portfolio demo:
    streamlit run app.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from store_analytics.config import DATABASE_PATH, LANGFUSE_ENABLED, LANGFUSE_HOST
from store_analytics.db.seed import seed_database

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CHARTS_DIR = DATA_DIR / "charts"

GATE_THRESHOLDS = {
    "tool_selection_accuracy": 0.85,
    "task_completion_rate": 0.80,
    "tool_validity_rate": 0.95,
    "no_hallucination_rate": 0.90,
    "error_handling_rate": 0.85,
    "trajectory_quality_avg": 0.60,
}

MAX_QUERIES_PER_SESSION = 15

st.set_page_config(page_title="Store Analytics Agent", page_icon="📊", layout="wide")

if not DATABASE_PATH.exists():
    seed_database(DATABASE_PATH)


@st.cache_data
def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def metric_row(label: str, value: float, threshold: float | None = None) -> None:
    if threshold is None:
        st.metric(label, f"{value:.1%}")
        return
    delta = value - threshold
    st.metric(label, f"{value:.1%}", delta=f"{delta:+.1%} vs gate", delta_color="normal" if delta >= 0 else "inverse")


tab_demo, tab_evals, tab_obs = st.tabs(["🤖 Agente en vivo", "📊 Dashboard de evals", "🔍 Observabilidad"])

# ---------------------------------------------------------------------------
# Tab 1: Agent demo
# ---------------------------------------------------------------------------
with tab_demo:
    st.subheader("Store Analytics Assistant")
    st.caption(
        "El agente decide entre 3 herramientas — `query_db` (SQL de solo lectura sobre una base "
        "fija), `web_search` y `calculator` — y se ve la trayectoria completa: qué ejecutó y por qué."
    )

    golden = load_json(DATA_DIR / "golden.json") or []
    example_queries = [c["input"] for c in golden[:12]] if golden else []

    col_a, col_b = st.columns([3, 1])
    with col_a:
        picked = st.selectbox("Pregunta de ejemplo", ["(escribir la mía)"] + example_queries)
        default_query = "" if picked == "(escribir la mía)" else picked
        query = st.text_input("Pregunta", value=default_query, placeholder="¿Cuál es el ingreso total de pedidos completados?")
    with col_b:
        st.write("")
        st.write("")
        run_clicked = st.button("Ejecutar", type="primary", width='stretch')

    st.session_state.setdefault("query_count", 0)

    if run_clicked and query.strip():
        if st.session_state.query_count >= MAX_QUERIES_PER_SESSION:
            st.warning("Límite de consultas por sesión alcanzado. Recarga la página para continuar.")
        else:
            st.session_state.query_count += 1
            try:
                from store_analytics.agent import run_agent

                with st.spinner("El agente está razonando..."):
                    result = run_agent(query.strip())

                st.markdown("#### Trayectoria")
                if not result.trajectory:
                    st.info("El agente respondió sin llamar a ninguna herramienta.")
                for i, tc in enumerate(result.trajectory, start=1):
                    status = "✅" if tc.success else "❌"
                    with st.expander(f"Paso {i}: {tc.tool_name} — {status} ({tc.latency_ms:.0f}ms)", expanded=True):
                        st.markdown("**Argumentos**")
                        st.code(json.dumps(tc.arguments, indent=2, ensure_ascii=False), language="json")
                        st.markdown("**Resultado**")
                        st.code(str(tc.result)[:1500], language="json")

                st.markdown("#### Respuesta final")
                st.success(result.final_answer)

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Tool calls", result.metadata.num_tool_calls)
                m2.metric("Latencia total", f"{result.metadata.latency_ms:.0f} ms")
                m3.metric("Tokens", result.metadata.total_tokens)
                m4.metric("Modelo", result.metadata.model_used or "—")
            except Exception as e:
                st.error(f"No se pudo ejecutar el agente: {e}")
                st.caption("Probablemente falten las API keys (GROQ_API_KEY) en los secrets del despliegue.")

# ---------------------------------------------------------------------------
# Tab 2: Evals dashboard
# ---------------------------------------------------------------------------
with tab_evals:
    st.subheader("Última corrida de evaluación")

    eval_results = load_json(DATA_DIR / "eval_results.json")
    if not eval_results:
        st.warning("No se encontró data/eval_results.json. Ejecuta `python scripts/run_evals.py` primero.")
    else:
        passed = eval_results.get("cases_passed", 0)
        total = eval_results.get("total_cases", 0)
        st.metric("Casos aprobados", f"{passed}/{total}", f"{passed/total:.0%}" if total else None)

        cols = st.columns(3)
        metric_keys = list(GATE_THRESHOLDS.items())
        for i, (key, threshold) in enumerate(metric_keys):
            label = key.replace("_", " ").title()
            with cols[i % 3]:
                metric_row(label, eval_results.get(key, 0.0), threshold)

        st.caption("El delta compara contra el umbral que usa `scripts/gate.py` para bloquear el merge en CI.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Radar de métricas")
            radar_path = CHARTS_DIR / "radar.png"
            if radar_path.exists():
                st.image(str(radar_path), width='stretch')
        with c2:
            st.markdown("##### Rendimiento por categoría")
            cat_path = CHARTS_DIR / "categories.png"
            if cat_path.exists():
                st.image(str(cat_path), width='stretch')

        st.markdown("##### Coste y latencia")
        l1, l2, l3 = st.columns(3)
        l1.metric("Latencia total", f"{eval_results.get('total_latency_ms', 0)/1000:.1f} s")
        l2.metric("Tokens totales", f"{eval_results.get('total_tokens', 0):,}")
        l3.metric("Tool calls totales", eval_results.get("total_tool_calls", 0))

        by_cat = eval_results.get("by_category", {})
        if by_cat:
            st.markdown("##### Detalle por categoría")
            rows = [
                {
                    "categoría": cat,
                    "n": d["count"],
                    "tool_selection": round(d["tool_selection"] / d["count"], 2),
                    "task_completion": round(d["task_completion"] / d["count"], 2),
                }
                for cat, d in sorted(by_cat.items())
            ]
            st.dataframe(rows, width='stretch', hide_index=True)

    st.divider()
    st.subheader("Composición del golden dataset")
    if golden:
        cat_counts = Counter(c["category"] for c in golden)
        diff_counts = Counter(c["difficulty"] for c in golden)
        d1, d2 = st.columns(2)
        with d1:
            st.caption(f"{len(golden)} casos totales, por categoría")
            st.bar_chart(cat_counts)
        with d2:
            st.caption("Por dificultad")
            st.bar_chart(diff_counts)
    else:
        st.info("No se encontró data/golden.json.")

    ab_results = load_json(DATA_DIR / "ab_results.json")
    if ab_results:
        st.divider()
        st.subheader(f"A/B: {ab_results['model_a']} vs {ab_results['model_b']}")
        ab_path = CHARTS_DIR / "ab_comparison.png"
        if ab_path.exists():
            st.image(str(ab_path), width='stretch')
        st.dataframe(
            [
                {"modelo": ab_results["model_a"], **ab_results["results_a"]},
                {"modelo": ab_results["model_b"], **ab_results["results_b"]},
            ],
            width='stretch',
            hide_index=True,
        )

# ---------------------------------------------------------------------------
# Tab 3: Observability
# ---------------------------------------------------------------------------
with tab_obs:
    st.subheader("Trazas y observabilidad")

    if LANGFUSE_ENABLED:
        st.success(f"Langfuse activo — trazas en tiempo real en [{LANGFUSE_HOST}]({LANGFUSE_HOST}).")
    else:
        st.info(
            "Langfuse no está configurado en este despliegue. Debajo se muestra un resumen derivado "
            "de la última corrida de evals como sustituto de las trazas en vivo."
        )

    eval_results = load_json(DATA_DIR / "eval_results.json")
    if eval_results and eval_results.get("cases"):
        cases = eval_results["cases"]

        tool_freq = Counter()
        for c in cases:
            for tc in c.get("trajectory", []):
                tool_freq[tc["tool_name"]] += 1

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Frecuencia de uso por herramienta")
            st.bar_chart(tool_freq)
        with c2:
            st.markdown("##### Latencia por caso (ms)")
            latencies = {c["id"]: c["metadata"].get("latency_ms", 0) for c in cases}
            st.bar_chart(latencies)

        st.markdown("##### Últimas trazas (derivadas de eval_results.json)")
        trace_rows = [
            {
                "caso": c["id"],
                "pregunta": c["input"][:60],
                "tool_calls": c["metadata"].get("num_tool_calls", 0),
                "tokens": c["metadata"].get("total_tokens", 0),
                "latencia_ms": round(c["metadata"].get("latency_ms", 0)),
                "modelo": c["metadata"].get("model_used", ""),
            }
            for c in cases
        ]
        st.dataframe(trace_rows, width='stretch', hide_index=True)
    else:
        st.warning("No hay datos de evals para derivar trazas. Ejecuta `python scripts/run_evals.py`.")
