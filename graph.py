"""El grafo de LangGraph que conecta todo.

    python graph.py "que tipos de exoplanetas existen"
    python graph.py "buscame planetas rocosos con temperaturas extremas"
    python graph.py "contame mas del primero"

El modelo interpreta y redacta; el grafo controla el flujo.
Todo el control de flujo es código testeable sin llamar a ningún modelo.
"""

from __future__ import annotations

import json
import os
import sys
from typing import TypedDict

from google import genai
import numpy as np
import pandas as pd
from langgraph.graph import StateGraph, END

from anomaly import (
    FEATURES, LOG_COLS, Z_THRESHOLD,
    prepare_features, score_anomalies, attribute, top_two_drivers, flag_quality,
)
from fetch_data import fetch
from kb_search import search as kb_search
from prompts import ROUTER, EXPLAIN, REPORT


# ── configuración de Gemini ──────────────────────────────────

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL = "gemini-3.6-flash"

MAX_RELAX_ATTEMPTS = 3
MIN_SUBSET = 50


# ── estado del grafo ─────────────────────────────────────────

class State(TypedDict, total=False):
    question: str
    intent: str
    confidence: float
    filters: dict
    subset: pd.DataFrame
    subset_size: int
    attempts: int
    relaxed: list[str]
    scored: pd.DataFrame
    kb_hits: str
    answer: str
    trace: list[str]


# ── helpers ──────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    """Una sola función para todas las llamadas a Gemini."""
    resp = _client.models.generate_content(model=_MODEL, contents=prompt)
    return resp.text.strip()


def _format_kb_hits(hits: pd.DataFrame) -> str:
    """Formatea los fragmentos de la KB para insertarlos en un prompt."""
    parts = []
    for _, row in hits.iterrows():
        parts.append(f"[{row['source']} — {row['section']}]\n{row['text']}")
    return "\n\n---\n\n".join(parts)


def _format_scored(df: pd.DataFrame, top_n: int = 10) -> str:
    """Formatea los resultados del scoring para el prompt de reporte."""
    lines = []
    for i, (_, row) in enumerate(df.head(top_n).iterrows(), 1):
        flag = f" ⚠ {row['quality_flag']}" if row.get("quality_flag", "") else ""
        lines.append(
            f"{i}. {row['pl_name']} — score={row['anomaly_score']:.3f}, "
            f"drivers={row['anomaly_type']}{flag}\n"
            f"   P={row['pl_orbper']:.1f}d R={row['pl_rade']:.1f}Re "
            f"M={row['pl_bmasse']:.1f}Me ρ={row['pl_dens']:.2f} "
            f"Teq={row['pl_eqt']:.0f}K e={row['pl_orbeccen']:.2f}"
        )
    return "\n".join(lines)


# ── nodos ────────────────────────────────────────────────────

def route(state: State) -> State:
    """Clasifica la intención del usuario con el LLM."""
    prompt = ROUTER.format(question=state["question"])
    raw = _call_llm(prompt)

    # Gemini a veces envuelve el JSON en ```json ... ```
    cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = {"intent": "ask_user", "confidence": 0.0}

    intent = parsed.get("intent", "ask_user")
    confidence = parsed.get("confidence", 0.0)

    # Si la confianza es muy baja, repreguntamos
    if confidence < 0.4:
        intent = "ask_user"

    trace = state.get("trace", [])
    trace.append(f"route → {intent} (conf={confidence:.2f})")

    return {**state, "intent": intent, "confidence": confidence, "trace": trace}


def node_kb_search(state: State) -> State:
    """Busca en la base de conocimiento."""
    hits = kb_search(state["question"], k=5)
    kb_text = _format_kb_hits(hits)

    trace = state.get("trace", [])
    trace.append(f"kb_search → {len(hits)} fragmentos")

    return {**state, "kb_hits": kb_text, "trace": trace}


def explain(state: State) -> State:
    """Redacta una respuesta de conocimiento con el LLM."""
    prompt = EXPLAIN.format(
        question=state["question"],
        kb_hits=state.get("kb_hits", "(sin fragmentos)"),
    )
    answer = _call_llm(prompt)

    trace = state.get("trace", [])
    trace.append("explain → respuesta generada")

    return {**state, "answer": answer, "trace": trace}


def parse_filters(state: State) -> State:
    """Traduce la pregunta del usuario a filtros sobre el catálogo.

    Le pide al LLM que devuelva un JSON con los filtros. Si no puede
    parsear la respuesta, deja filtros vacíos (se analiza todo).
    """
    prompt = f"""\
Traducí esta pregunta a filtros sobre un catálogo de exoplanetas.
Devolvé SOLO un JSON con los filtros aplicables. Las columnas disponibles son:
- pl_orbper: período orbital en días
- pl_rade: radio en radios terrestres (rocoso < 1.6, super-Tierra 1.6-4, gigante > 4)
- pl_bmasse: masa en masas terrestres
- pl_dens: densidad en g/cm³
- pl_eqt: temperatura de equilibrio en Kelvin (caliente > 1000, templado 200-400)
- pl_orbeccen: excentricidad (0 = circular, > 0.3 = excéntrica)
- discoverymethod: método de descubrimiento (Transit, Radial Velocity, etc.)
- st_teff: temperatura de la estrella en K (fría < 3500, solar 5000-6000)

Formato del JSON: {{"columna": {{"op": "valor"}}}}
Operadores: "gt", "lt", "gte", "lte", "eq", "between" (con lista [min, max])

Ejemplo para "planetas rocosos calientes":
{{"pl_rade": {{"lt": 1.6}}, "pl_eqt": {{"gt": 1000}}}}

Si la pregunta es muy general ("buscame planetas raros"), devolvé {{}}.

Pregunta: {state["question"]}
"""
    raw = _call_llm(prompt)
    cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        filters = json.loads(cleaned)
    except json.JSONDecodeError:
        filters = {}

    trace = state.get("trace", [])
    trace.append(f"parse_filters → {filters if filters else 'sin filtros'}")

    return {
        **state,
        "filters": filters,
        "attempts": 0,
        "relaxed": [],
        "trace": trace,
    }


def query(state: State) -> State:
    """Filtra el catálogo según los filtros parseados."""
    df = fetch()
    df = df.dropna(subset=FEATURES)
    total = len(df)

    filters = state.get("filters", {})
    for col, condition in filters.items():
        if col not in df.columns:
            continue
        for op, val in condition.items():
            if op == "gt":
                df = df[df[col] > val]
            elif op == "lt":
                df = df[df[col] < val]
            elif op == "gte":
                df = df[df[col] >= val]
            elif op == "lte":
                df = df[df[col] <= val]
            elif op == "eq":
                df = df[df[col] == val]
            elif op == "between" and isinstance(val, list) and len(val) == 2:
                df = df[(df[col] >= val[0]) & (df[col] <= val[1])]

    trace = state.get("trace", [])
    trace.append(f"query → {len(df)} planetas (de {total} completos)")

    return {**state, "subset": df, "subset_size": len(df), "trace": trace}


def relax(state: State) -> State:
    """Afloja el filtro más restrictivo un escalón.

    Estrategia: el filtro que más reduce el dataset se afloja un 30%.
    Si es un "gt", se baja; si es un "lt", se sube.
    """
    filters = state.get("filters", {}).copy()
    attempts = state.get("attempts", 0) + 1
    relaxed = list(state.get("relaxed", []))

    df_full = fetch().dropna(subset=FEATURES)

    # Buscar cuál filtro descarta más planetas
    most_restrictive = None
    most_removed = 0

    for col, condition in filters.items():
        if col not in df_full.columns:
            continue
        remaining = df_full.copy()
        for op, val in condition.items():
            if op == "gt":
                remaining = remaining[remaining[col] > val]
            elif op == "lt":
                remaining = remaining[remaining[col] < val]
            elif op == "gte":
                remaining = remaining[remaining[col] >= val]
            elif op == "lte":
                remaining = remaining[remaining[col] <= val]

        removed = len(df_full) - len(remaining)
        if removed > most_removed:
            most_removed = removed
            most_restrictive = col

    if most_restrictive and most_restrictive in filters:
        cond = filters[most_restrictive]
        for op in list(cond.keys()):
            val = cond[op]
            if isinstance(val, (int, float)):
                if op in ("gt", "gte"):
                    cond[op] = val * 0.7
                elif op in ("lt", "lte"):
                    cond[op] = val * 1.3
        filters[most_restrictive] = cond
        relaxed.append(f"{most_restrictive}: aflojado 30%")

    trace = state.get("trace", [])
    trace.append(f"relax → intento {attempts}, aflojé {most_restrictive}")

    return {
        **state,
        "filters": filters,
        "attempts": attempts,
        "relaxed": relaxed,
        "trace": trace,
    }


def score(state: State) -> State:
    """Corre Isolation Forest y atribución sobre el subconjunto."""
    df = state["subset"].copy()

    X = prepare_features(df)
    df["anomaly_score"] = score_anomalies(X)

    zscores = attribute(df)
    z_cols = zscores.columns.tolist()
    df = pd.concat([df, zscores], axis=1)
    df["anomaly_type"] = df.apply(lambda row: top_two_drivers(row, z_cols), axis=1)
    df["quality_flag"] = flag_quality(df)

    scored = df.sort_values("anomaly_score", ascending=False)

    trace = state.get("trace", [])
    n_flagged = (scored.head(10)["quality_flag"] != "").sum()
    n_combo = (scored.head(10)["anomaly_type"] == "combinación").sum()
    trace.append(f"score → top 10: {n_flagged} flagged, {n_combo} combinación")

    return {**state, "scored": scored, "trace": trace}


def observability(state: State) -> State:
    """Agrega info de observabilidad al reporte.

    TSM y ESM ya están en el catálogo (no las calculamos nosotros).
    Por ahora las incluimos en el scored si están disponibles.
    """
    scored = state["scored"].copy()

    trace = state.get("trace", [])
    n_with_tsm = scored.head(10)["pl_tsm"].notna().sum() if "pl_tsm" in scored.columns else 0
    trace.append(f"observability → {n_with_tsm}/10 del top con TSM")

    return {**state, "scored": scored, "trace": trace}


def report(state: State) -> State:
    """Redacta el informe de análisis con el LLM."""
    scored = state["scored"]
    total_df = fetch()
    relaxed = state.get("relaxed", [])
    relaxed_note = ""
    if relaxed:
        relaxed_note = "- Se aflojaron filtros: " + "; ".join(relaxed)

    filters_str = json.dumps(state.get("filters", {}), ensure_ascii=False)
    if filters_str == "{}":
        filters_str = "ninguno (catálogo completo)"

    prompt = REPORT.format(
        question=state["question"],
        subset_size=state["subset_size"],
        total_size=len(total_df),
        filters=filters_str,
        relaxed_note=relaxed_note,
        scored=_format_scored(scored),
    )
    answer = _call_llm(prompt)

    trace = state.get("trace", [])
    trace.append("report → respuesta generada")

    return {**state, "answer": answer, "trace": trace}


def followup(state: State) -> State:
    """Responde sobre resultados que ya están en el estado."""
    scored = state.get("scored")
    if scored is None or (hasattr(scored, "empty") and scored.empty):
        return {
            **state,
            "answer": "Todavía no hice ningún análisis en esta conversación. "
                      "¿Querés que busque algo?",
            "trace": state.get("trace", []) + ["followup → sin datos previos"],
        }

    context = _format_scored(scored)
    prompt = f"""\
El usuario pregunta sobre resultados que ya calculamos.
Respondé en español, con los datos que tenés. Si no tenés la info, decilo.

Resultados previos:
{context}

Pregunta del usuario:
{state["question"]}
"""
    answer = _call_llm(prompt)

    trace = state.get("trace", [])
    trace.append("followup → respuesta sobre datos previos")

    return {**state, "answer": answer, "trace": trace}


def ask_user(state: State) -> State:
    """No se entendió la pregunta, pide que reformule."""
    return {
        **state,
        "answer": "No estoy seguro de qué querés hacer. ¿Podrías reformular la pregunta? "
                  "Puedo explicarte sobre tipos de exoplanetas, buscar planetas raros "
                  "en el catálogo, o contarte más sobre un resultado anterior.",
        "trace": state.get("trace", []) + ["ask_user → repreguntando"],
    }


# ── decisiones de ruteo (deterministas) ──────────────────────

def after_route(state: State) -> str:
    """Decide qué nodo sigue según la intención clasificada."""
    intent = state.get("intent", "ask_user")
    if intent == "knowledge":
        return "kb_search"
    elif intent == "analysis":
        return "parse_filters"
    elif intent == "followup":
        return "followup"
    else:
        return "ask_user"


def after_query(state: State) -> str:
    """El ciclo: si hay pocos planetas y quedan intentos, relaja."""
    size = state.get("subset_size", 0)
    attempts = state.get("attempts", 0)
    if size < MIN_SUBSET and attempts < MAX_RELAX_ATTEMPTS:
        return "relax"
    return "score"


# ── construcción del grafo ───────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(State)

    g.add_node("route", route)
    g.add_node("kb_search", node_kb_search)
    g.add_node("explain", explain)
    g.add_node("parse_filters", parse_filters)
    g.add_node("query", query)
    g.add_node("relax", relax)
    g.add_node("score", score)
    g.add_node("observability", observability)
    g.add_node("report", report)
    g.add_node("followup", followup)
    g.add_node("ask_user", ask_user)

    g.set_entry_point("route")

    # Después del router: camino determinista según intent
    g.add_conditional_edges("route", after_route)

    # Camino de conocimiento: kb_search → explain → fin
    g.add_edge("kb_search", "explain")
    g.add_edge("explain", END)

    # Camino de análisis: parse_filters → query → (relax|score)
    g.add_edge("parse_filters", "query")
    g.add_conditional_edges("query", after_query)
    g.add_edge("relax", "query")  # el ciclo
    g.add_edge("score", "observability")
    g.add_edge("observability", "report")
    g.add_edge("report", END)

    # Caminos directos al final
    g.add_edge("followup", END)
    g.add_edge("ask_user", END)

    return g.compile()


# ── ejecución ────────────────────────────────────────────────

_graph = build_graph()


def run(question: str, scored: pd.DataFrame | None = None) -> dict:
    """Ejecuta el grafo con una pregunta.

    scored: resultados de una corrida anterior, para followup.
    """
    initial: State = {"question": question, "trace": []}
    if scored is not None:
        initial["scored"] = scored

    result = _graph.invoke(initial)
    return result


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Re-crear el cliente con la key cargada de .env
    _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

    q = " ".join(sys.argv[1:]) or "que tipos de exoplanetas existen"
    print(f"pregunta: {q}\n")

    result = run(q)

    print("─" * 60)
    print(result.get("answer", "(sin respuesta)"))
    print("─" * 60)
    print("\ntraza:")
    for step in result.get("trace", []):
        print(f"  → {step}")
