# Auditoría del proyecto — 2026-09-21

Registro de la revisión de bugs/huecos hecha sobre Store Analytics Agent y de los fixes aplicados en esa sesión.

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

- **`no_hallucinated_numbers`** (`metrics.py`) compara números como strings extraídos por regex; diferencias de formato/redondeo entre SQLite y la respuesta del LLM pueden generar falsos positivos de "alucinación".
- **`judge.py`** usa `re.search(r'\{[^}]+\}', ...)` para extraer JSON de la respuesta de Mistral — no soporta JSON con llaves anidadas, podría cortar mal el parseo en algunos casos.
- **`web_search.py`** tiene datos cacheados con fecha fija ("septiembre 2026") que quedarán obsoletos sin aviso.
- **`llm.py`** no tiene retries/timeouts explícitos para las llamadas a Groq/Mistral — un fallo de red tira el EVAL completo sin reintento.
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
