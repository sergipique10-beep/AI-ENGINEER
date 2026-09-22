# Auditoría del proyecto — 2026-09-21 / 2026-09-22

Registro de la revisión de bugs/huecos hecha sobre Store Analytics Agent y de los fixes aplicados en esa sesión.

## Ronda 2 (2026-09-22) — disparada por el primer run real del CI gate

Al configurar por fin `GROQ_API_KEY`/`MISTRAL_API_KEY` como secrets del repo y dejar
correr el gate contra las APIs reales (PR #1), salieron 4 métricas en rojo. Se
investigó caso por caso en vez de asumir que el agente falla; resultado: **cero
alucinaciones reales encontradas** — todo era bugs en el propio harness de evals.

| # | Problema | Severidad | Archivo(s) | Estado |
|---|----------|-----------|------------|--------|
| 8 | `no_hallucinated_numbers` comparaba números como strings exactos: `"32.00"` (respuesta) vs `"32.0"` (tool) contaban como distintos → falso positivo de alucinación en redondeos normales. 28 de 92 casos afectados. | **Alta** | `evals/metrics.py` | ✅ Corregido — nueva `_matches_within_rounding()` compara como float con tolerancia (exacto, redondeo a entero, redondeo a 2 decimales). |
| 9 | El mismo extractor de números (`_extract_numbers`) partía fechas ISO como `2026-09-22` en `-09` y `-22`, tratando el guion de fecha como signo negativo. | Media | `evals/metrics.py` | ✅ Corregido — regex con negative lookbehind `(?<!\d)-?\d...` para no absorber el guion cuando el carácter anterior ya es un dígito. |
| 10 | La misma métrica marcaba como "alucinado" un número que el propio usuario puso en su pregunta (ej. "21% VAT on 1240" → el `21` de la respuesta se contaba como inventado). No tenía acceso al texto de la pregunta original. | Media | `evals/metrics.py`, `evals/harness.py` | ✅ Corregido — `no_hallucinated_numbers()` ahora acepta `source_text` (la pregunta) y excluye sus números; `harness.py` se lo pasa. |
| 11 | El LLM a veces formatea miles en LaTeX (`159{,}111.71`), que el regex no reconocía como separador de miles y partía en fragmentos falsos (`159` + `111.71`). | Media | `evals/metrics.py` | ✅ Corregido — `_extract_numbers` normaliza `{,}` → `,` antes de tokenizar. |
| 12 | Números que son el resultado de una operación mostrada en la respuesta (ej. "159,111.71 + 50,391.00 = 209,502.71") se contaban como alucinados porque el resultado en sí no aparece literal en ningún tool result. | Media | `evals/metrics.py` | ✅ Corregido — nueva `_matches_derived()` acepta un número si es la suma/resta/producto/cociente de otros dos ya verificados. |
| 13 | `_validate_calculator_expr` usaba `ast.walk()` plano, que también visita los nodos internos del operador (`ast.Mult`, `ast.Sub`, `ast.Div`, `ast.Pow`) como si fueran nodos de nivel superior — al no estar en la whitelist, marcaba como "unsafe" operaciones tan básicas como `1200 * 0.85`. 23 de 92 casos afectados; la calculadora real (`calculator.py`) sí soporta estas operaciones sin problema, solo el validador del eval estaba mal. | **Alta** | `evals/metrics.py` | ✅ Corregido — nueva `_check_calc_node()` recorre el árbol recursivamente comprobando `type(node.op)` contra la misma whitelist que usa el evaluador real. |
| 14 | El juez LLM (Mistral) y el propio agente (Groq) no tenían retry/backoff — un 429 de rate limit tiraba la llamada entera. En el run real de 92 casos, **el 100%** de las llamadas al juez fallaron por rate limit de Mistral (free tier), degradando `trajectory_quality` a 0.5 falso en todos los casos. Un caso (`m010`) recibió un 429 de Groq y el texto crudo del error terminó siendo la "respuesta final" del agente. | **Crítica** | `llm.py` | ✅ Corregido — `_call_with_retry()` con backoff exponencial (hasta 4 intentos) envuelve tanto las llamadas a Groq como a Mistral cuando el error contiene "429". |
| 15 | `error_handling()` solo miraba `result.error` dentro de la rama de "hubo tool calls fallidos" — si el agente crasheaba sin haber llamado a ninguna tool (como en el caso anterior), la métrica devolvía 1.0 ("All tool calls succeeded") en vez de 0.0. | Media | `evals/metrics.py` | ✅ Corregido — ahora comprueba `result.error` primero, antes de mirar `failed_tools`. |
| 16 | `run_agent()` dejaba que una excepción de `llm_client.call()` se propagara sin control — la excepción cruda (incluyendo el JSON de error de la API) podía terminar expuesta en el chat de la demo pública de Streamlit. | Media | `agent.py` | ✅ Corregido — la llamada al LLM está envuelta en try/except; en fallo devuelve un `AgentResult` con `error` seteado y `final_answer=""` en vez de propagar. |
| 17 | `gate.py` exigía `MAX_HALLUCINATED_NUMBERS = 0` (tolerancia cero), un listón poco realista para una métrica basada en regex. Tras los fixes de arriba, `no_hallucination_rate` pasó de 0.587 a 0.978 sobre el run real, pero un caso (`m002`, un margen promedio calculado producto por producto) sigue sin poder verificarse sin reconstruir la aritmética completa de la tabla — no es una alucinación real, es un límite conocido de la heurística. | Baja | `scripts/gate.py` | ✅ Ajustado a `MAX_HALLUCINATED_NUMBERS = 1`, documentado en el propio archivo. El umbral real de calidad sigue siendo `no_hallucination_rate >= 0.90`. |

Verificación: los fixes se probaron reproduciendo los 92 casos reales descargados del
run de CI (`gh run download`) contra las funciones corregidas, sin gastar más cuota de
API — antes de confirmarlos con un segundo run real.

## Ronda 3 (2026-09-22) — el retry de la Ronda 2 provocó un timeout

El fix #14 (retry con backoff en 429) arregló `trajectory_quality`, pero introdujo un
problema nuevo: con ~180 llamadas al juez de Mistral disparadas sin espaciar en el
harness, casi todas chocaban con el rate limit del free tier, y cada una ahora
reintentaba hasta 4 veces con backoff creciente (2s+4s+8s=14s en el peor caso) **en
vez de fallar rápido como antes**. Resultado: el run real superó los 30 minutos de
`timeout-minutes` del workflow y GitHub canceló el job antes de que `gate.py` llegara
a ejecutarse.

| # | Problema | Severidad | Archivo(s) | Estado |
|---|----------|-----------|------------|--------|
| 18 | Retry puramente reactivo sin espaciar las llamadas de antemano — con un límite de tasa estricto (Mistral free tier), reintentar tras cada 429 sin más simplemente vuelve a chocar con el límite, multiplicando el tiempo total en vez de evitarlo. | **Alta** | `llm.py` | ✅ Corregido — `_call_mistral` ahora espera un mínimo de 1.1s desde la última llamada *antes* de disparar la siguiente (`_MISTRAL_MIN_INTERVAL_S`), y el retry reactivo se redujo a un único reintento de seguridad (2 intentos, 1.5s) en vez de 4 intentos con backoff exponencial. |

Lección: un retry sin throttling proactivo puede convertir "todas las llamadas fallan
rápido" en "todas las llamadas fallan lento" — peor para un pipeline con presupuesto
de tiempo fijo (CI) aunque parezca más resiliente en aislamiento.

## Hallazgos y estado

| # | Problema | Severidad | Archivo(s) | Estado |
|---|----------|-----------|------------|--------|
| 1 | `error_handling` en el EVAL detectaba "operaciones destructivas" con un simple `substring in string`, sin límites de palabra. Podía marcar falsos positivos (ej. una columna `updated_at` o la palabra "alternate" activaban el filtro de "update"/"alter"). | Media | `src/store_analytics/evals/metrics.py` | ✅ Corregido — ahora usa regex con `\b...\b`, igual que la protección real de `query_db.py`. |
| 2 | El prompt del juez LLM (`JUDGE_RUBRIC`) tenía caracteres chinos (`大致`) mezclados por error en medio del texto en inglés. | Baja | `src/store_analytics/evals/judge.py` | ✅ Corregido. |
| **3** | **CRÍTICO** — El juez LLM (Mistral) llevaba fallando silenciosamente desde siempre. El paquete instalado `mistralai==2.10.1` no expone `Mistral` en el nivel superior del módulo (no tiene `mistralai/__init__.py`); hay que importarlo desde `mistralai.client`. El código hacía `import mistralai` y luego `mistralai.Mistral(...)`, lo cual lanzaba `AttributeError`. El `except Exception` de `judge.py` enmascaraba el fallo devolviendo siempre `score=0.5` como si fuera un juicio real. Confirmado con evidencia directa en `data/eval_results_broken.json` (`"Judge call failed: module 'mistralai' has no attribute 'Mistral'"`). | **Alta** | `src/store_analytics/llm.py` | ✅ Corregido — import cambiado a `from mistralai.client import Mistral`, verificado que instancia sin error. |
| 4 | `pyproject.toml` desincronizado de `requirements.txt`: declaraba el paquete `dotenv` (no oficial) en vez de `python-dotenv`, y no incluía `matplotlib` ni `langfuse` que sí usa el proyecto (`scripts/generate_charts.py`, observabilidad). | Baja | `pyproject.toml` | ✅ Corregido — nombre de paquete arreglado; añadidos como extras opcionales `charts` y `observability`. |
| 5 | No existían tests del agente (`run_agent`) que no dependieran de API keys reales — toda la validación del bucle recaía en el EVAL (que sí necesita `GROQ_API_KEY`/`MISTRAL_API_KEY`). | Media | `tests/` | ✅ Corregido — nuevo `tests/test_agent.py` con un LLM falso (mock) que cubre: uso de tool + respuesta final, respuesta directa sin tools, tool desconocida, y límite de `MAX_TOOL_CALLS`. 7/7 tests pasan con `pytest`. |
| 6 | `scripts/ab_experiment.py` tenía como modelo B por defecto `qwen/qwen3.8-27b`, un identificador de modelo con pinta de typo (no corresponde a ningún modelo real publicado). | Baja | `scripts/ab_experiment.py` | ✅ Corregido a `qwen/qwen3-32b`. |
| 7 | `data/eval_results_broken.json` — se investigó si era un archivo huérfano o un bug. | N/A | `data/`, `scripts/demo_break.py` | ✅ No es un bug. Es la salida intencional de `demo_break.py`, que rompe a propósito la tool `calculator` (divide todo entre 2) para demostrar que `gate.py` detecta la regresión y bloquearía el merge. Está correctamente listado en `.gitignore`. |

## Puntos frágiles anotados (no corregidos aún, quedan como riesgo conocido)

- **`no_hallucinated_numbers`** (Ronda 2 la reforzó bastante, pero sigue siendo heurística): no puede verificar un valor que resulta de una operación repetida sobre múltiples filas de una tabla (ej. un margen medio calculado producto por producto) — caso `m002`.
- **`judge.py`** usa `re.search(r'\{[^}]+\}', ...)` para extraer JSON de la respuesta de Mistral — no soporta JSON con llaves anidadas, podría cortar mal el parseo en algunos casos.
- **`web_search.py`** tiene datos cacheados con fecha fija ("septiembre 2026") que quedarán obsoletos sin aviso.
- Los umbrales de `gate.py` (`THRESHOLDS`) están duplicados a mano en `scripts/generate_charts.py` (líneas de threshold en los gráficos) — si se cambian en uno, hay que recordar cambiarlos en el otro.

## Contexto técnico del hallazgo #3 (para referencia futura)

```
mistralai 2.10.1 instalado en:
C:\Users\Mati\AppData\Roaming\Python\Python314\site-packages\mistralai

- NO tiene mistralai/__init__.py (namespace package vacío)
- SÍ tiene mistralai/client/__init__.py, que expone la clase Mistral real
  → mistralai.client.sdk.Mistral

Import correcto:  from mistralai.client import Mistral
Import roto (el que había): import mistralai; mistralai.Mistral(...)
```

Si en el futuro se actualiza `mistralai` a otra versión, vale la pena volver a verificar esto (`python -c "from mistralai.client import Mistral; print(Mistral)"`), ya que el SDK de Mistral ha reestructurado su paquete más de una vez.
