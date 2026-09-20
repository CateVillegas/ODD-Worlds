"""Interfaz web de Odd Worlds."""

from __future__ import annotations

import os
import sqlite3
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import gradio as gr
import pandas as pd
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

import odd_worlds.agent.graph as graph_module
from odd_worlds.agent.graph import build_graph

graph_module._client = graph_module.genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY", ""),
)

print("cargando modelo de embeddings...", flush=True)
from odd_worlds.kb.search import load as _preload_kb
_preload_kb()
print("listo", flush=True)

DB_PATH = Path("data/conversations.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
_saver = SqliteSaver(conn=_conn)
_graph = build_graph(checkpointer=_saver)

_threads: dict[str, dict] = {}

# ── Dataset ──

_catalog = pd.read_csv("data/cache/pscomppars.csv", comment="#")

_SHOW_COLS = {
    "pl_name": "Planeta",
    "hostname": "Estrella",
    "discoverymethod": "Metodo",
    "disc_year": "Anio",
    "pl_rade": "Radio (R⊕)",
    "pl_bmasse": "Masa (M⊕)",
    "pl_eqt": "T eq (K)",
    "pl_orbper": "Periodo (dias)",
    "pl_dens": "Densidad (g/cm³)",
    "pl_tsm": "TSM",
    "pl_esm": "ESM",
    "pl_controv_flag": "Controvertido",
}
_existing = [c for c in _SHOW_COLS if c in _catalog.columns]
_display_df = _catalog[_existing].copy()
_display_df.columns = [_SHOW_COLS[c] for c in _existing]

# ── Suggestions ──

SUGGESTIONS = [
    "Que exoplanetas estan en la zona habitable?",
    "Como funciona el metodo de transito?",
    "Buscame los mundos mas raros",
    "Que tipos de planetas existen?",
]


def _new_thread() -> str:
    tid = uuid.uuid4().hex[:12]
    _threads[tid] = {
        "title": "Nueva conversacion",
        "created": datetime.now().strftime("%H:%M"),
    }
    return tid


def _split_bubbles(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text.strip()]

    bubbles: list[str] = []
    for p in paragraphs:
        words = p.split()
        if len(words) <= 35:
            bubbles.append(p)
        else:
            sentences = p.replace(". ", ".\n").split("\n")
            current: list[str] = []
            current_len = 0
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                wc = len(s.split())
                if current_len + wc > 35 and current:
                    bubbles.append(" ".join(current))
                    current = [s]
                    current_len = wc
                else:
                    current.append(s)
                    current_len += wc
            if current:
                bubbles.append(" ".join(current))

    return bubbles[:8] if bubbles else [text.strip()]


def respond(message: str, history: list[dict], thread_id: str):
    if not message or not message.strip():
        yield "", history, thread_id
        return

    if not thread_id or thread_id not in _threads:
        thread_id = _new_thread()

    history = history + [{"role": "user", "content": message}]
    history_typing = history + [{"role": "assistant", "content": "..."}]
    yield "", history_typing, thread_id

    try:
        result = _graph.invoke(
            {"question": message, "trace": []},
            config={"configurable": {"thread_id": thread_id}},
        )
        answer = result.get("answer", "No pude generar una respuesta.")
        trace = result.get("trace", [])
        print(f"[respond] traza: {trace}", flush=True)
    except Exception as e:
        print(f"[respond] error: {e}", flush=True)
        traceback.print_exc()
        answer = "Hubo un error procesando tu pregunta. Proba de nuevo."

    if _threads[thread_id]["title"] == "Nueva conversacion":
        _threads[thread_id]["title"] = message[:30]

    history_clean = [m for m in history if m.get("content") != "..."]
    bubbles = _split_bubbles(answer)

    for bubble in bubbles:
        history_clean = history_clean + [{"role": "assistant", "content": bubble}]

    yield "", history_clean, thread_id


def _make_suggestion_handler(text: str):
    def handler(history, thread_id):
        yield from respond(text, history, thread_id)
    return handler


def new_conversation():
    tid = _new_thread()
    return "", [], tid


# ── Tema ──

SPACE_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.purple,
    secondary_hue=gr.themes.colors.purple,
    neutral_hue=gr.themes.colors.slate,
    font=gr.themes.GoogleFont("Inter"),
).set(
    body_background_fill="#0b0f1e",
    body_background_fill_dark="#0b0f1e",
    body_text_color="#e5e7f0",
    body_text_color_dark="#e5e7f0",
    body_text_color_subdued="#7b86a8",
    body_text_color_subdued_dark="#7b86a8",
    background_fill_primary="#13182d",
    background_fill_primary_dark="#13182d",
    background_fill_secondary="#1c2440",
    background_fill_secondary_dark="#1c2440",
    border_color_primary="#2a3250",
    border_color_primary_dark="#2a3250",
    border_color_accent="#8b5cf6",
    border_color_accent_dark="#8b5cf6",
    border_color_accent_subdued="#6d28d9",
    border_color_accent_subdued_dark="#6d28d9",
    color_accent_soft="#2e1065",
    color_accent_soft_dark="#2e1065",
    block_background_fill="#13182d",
    block_background_fill_dark="#13182d",
    block_border_color="#2a3250",
    block_border_color_dark="#2a3250",
    block_label_text_color="#7b86a8",
    block_label_text_color_dark="#7b86a8",
    block_title_text_color="#e5e7f0",
    block_title_text_color_dark="#e5e7f0",
    input_background_fill="#191f38",
    input_background_fill_dark="#191f38",
    input_border_color="#2a3250",
    input_border_color_dark="#2a3250",
    input_border_color_focus="#8b5cf6",
    input_border_color_focus_dark="#8b5cf6",
    input_placeholder_color="#7b86a8",
    input_placeholder_color_dark="#7b86a8",
    button_primary_background_fill="linear-gradient(135deg, #8b5cf6, #7c3aed)",
    button_primary_background_fill_dark="linear-gradient(135deg, #8b5cf6, #7c3aed)",
    button_primary_text_color="#ffffff",
    button_primary_text_color_dark="#ffffff",
    button_primary_border_color="transparent",
    button_primary_border_color_dark="transparent",
    button_secondary_background_fill="#191f38",
    button_secondary_background_fill_dark="#191f38",
    button_secondary_text_color="#e5e7f0",
    button_secondary_text_color_dark="#e5e7f0",
    shadow_drop="none",
    shadow_drop_lg="none",
)

CSS = """
/* ── Nebula background ── */
body {
    background:
        radial-gradient(ellipse at 15% 50%, rgba(139,92,246,0.07) 0%, transparent 50%),
        radial-gradient(ellipse at 85% 20%, rgba(99,102,241,0.05) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 85%, rgba(139,92,246,0.04) 0%, transparent 45%),
        #0b0f1e !important;
    background-attachment: fixed !important;
}

/* ── Viewport layout ── */
html, body { height: 100% !important; margin: 0 !important; overflow: hidden !important; }
.gradio-container {
    height: 100vh !important; max-height: 100vh !important;
    display: flex !important; flex-direction: column !important;
    overflow: hidden !important; max-width: 100% !important;
    padding: 0 1rem !important; background: transparent !important;
}
.gradio-container > .main {
    flex: 1 !important; display: flex !important; flex-direction: column !important;
    overflow: hidden !important; min-height: 0 !important;
    background: transparent !important;
}
.gradio-container > .main > .wrap {
    flex: 1 !important; display: flex !important; flex-direction: column !important;
    overflow: hidden !important; min-height: 0 !important; gap: 0 !important;
}

/* ── Scrollbar ── */
* { scrollbar-width: thin; scrollbar-color: #2a3250 transparent; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: #2a3250; border-radius: 999px; }
::-webkit-scrollbar-track { background: transparent; }

/* ── Top bar ── */
.top-bar {
    padding: 0.3rem 0.5rem !important;
    align-items: center !important;
    flex-shrink: 0 !important;
    gap: 0 !important;
}
.app-header { flex: 1; text-align: center; }
.app-header h1 {
    font-size: 1.15rem; font-weight: 700;
    background: linear-gradient(135deg, #8b5cf6, #a78bfa, #c4b5fd);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0;
}
.app-header p { color: #7b86a8; font-size: 0.65rem; margin: 0.05rem 0 0; }
.new-chat-btn {
    border-radius: 20px !important; font-size: 0.7rem !important;
    padding: 0.3rem 0.8rem !important; min-height: unset !important;
    height: auto !important; white-space: nowrap !important;
}

/* ── Tabs ── */
.main-tabs { flex: 1 !important; min-height: 0 !important; overflow: hidden !important;
    display: flex !important; flex-direction: column !important; }
.main-tabs > .tab-nav { flex-shrink: 0 !important; }
.main-tabs > .tabitem {
    flex: 1 !important; min-height: 0 !important; overflow: hidden !important;
    display: flex !important; flex-direction: column !important;
}

/* ── Chatbot: fixed height, internal scroll ── */
.chatbot-area {
    border-radius: 16px !important;
    flex: 1 !important;
    min-height: 200px !important;
    overflow: hidden !important;
}

/* HIDE any chatbot header/label bar */
.chatbot-area .label-wrap,
.chatbot-area .block-label,
.chatbot-area > .block > .block-label,
.chatbot-area > div > .label-wrap { display: none !important; }

/* ── Bubbles ── */
.chatbot-area .bot { border-radius: 18px 18px 18px 4px !important; }
.chatbot-area .user { border-radius: 18px 18px 4px 18px !important; }

/* ── Hide Gradio chrome ── */
.chatbot-area .icon-button-wrapper,
.chatbot-area .message-buttons-right,
.chatbot-area .message-buttons-left { display: none !important; }
footer { display: none !important; }

/* ── Chatbot examples (suggestions inside chatbot) ── */
.chatbot-area .example-btn {
    border-radius: 12px !important;
    font-size: 0.78rem !important;
    background: rgba(19,24,45,0.6) !important;
    border: 1px solid rgba(42,50,80,0.7) !important;
    color: rgba(229,231,240,0.85) !important;
}
.chatbot-area .example-btn:hover {
    border-color: rgba(139,92,246,0.4) !important;
    background: rgba(19,24,45,0.95) !important;
}

/* ── Input ── */
.input-area {
    flex-shrink: 0 !important; gap: 8px !important;
    align-items: flex-end !important; padding: 0.3rem 0 !important;
    max-width: 42rem !important; margin: 0 auto !important;
    width: 100% !important;
}
.input-area textarea {
    border-radius: 22px !important; padding: 10px 18px !important;
    min-height: 44px !important; resize: none !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.input-area textarea:focus {
    border-color: #8b5cf6 !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.25) !important;
}

/* ── Send button ── */
.send-btn {
    border-radius: 50% !important; min-width: 44px !important;
    max-width: 44px !important; height: 44px !important;
    padding: 0 !important; font-size: 1.1rem !important;
    display: flex !important; align-items: center !important;
    justify-content: center !important; flex-shrink: 0 !important;
}

/* ── Animations ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
.chatbot-area .message-row { animation: fadeUp 0.25s ease-out !important; }

/* ── Links ── */
.chatbot-area a { color: #a78bfa !important; }
.chatbot-area em { color: #a78bfa !important; }

/* ── Disclaimer ── */
.disclaimer {
    color: #7b86a8 !important; font-size: 0.6rem !important;
    text-align: center !important; padding: 0.1rem 0 !important;
    margin: 0 !important; flex-shrink: 0 !important;
}

/* ── Dataset tab ── */
.dataset-header {
    text-align: center; padding: 0.6rem 0 0.3rem;
}
.dataset-header .count {
    font-size: 1.5rem; font-weight: 700; color: #8b5cf6;
}
.dataset-header .label {
    color: #7b86a8; font-size: 0.8rem;
}
.dataset-table {
    border-radius: 12px !important; overflow: hidden !important;
    flex: 1 !important; min-height: 0 !important;
}
.dataset-table .table-wrap {
    max-height: calc(100vh - 200px) !important;
    overflow: auto !important;
}
.dataset-table table { border-collapse: collapse !important; width: 100% !important; }
.dataset-table th {
    background: #1c2440 !important;
    color: #a78bfa !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    padding: 0.55rem 0.7rem !important;
    border-bottom: 2px solid rgba(139,92,246,0.3) !important;
    text-align: left !important;
    position: sticky !important; top: 0 !important; z-index: 1 !important;
}
.dataset-table td {
    padding: 0.4rem 0.7rem !important;
    font-size: 0.75rem !important;
    border-bottom: 1px solid rgba(42,50,80,0.5) !important;
    color: #e5e7f0 !important;
}
.dataset-table tr:nth-child(even) td {
    background: rgba(19,24,45,0.4) !important;
}
.dataset-table tr:hover td {
    background: rgba(139,92,246,0.08) !important;
}
"""


EMPTY_STATE_HTML = (
    '<div style="display:flex; flex-direction:column; align-items:center; '
    'gap:1rem; padding:2.5rem 1rem; text-align:center;">'
    '<div style="width:48px; height:48px; border-radius:12px; '
    'background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.3); '
    'display:flex; align-items:center; justify-content:center;">'
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
    'stroke="#8b5cf6" stroke-width="1.5" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>'
    '<path d="M2 12h20"/>'
    '</svg></div>'
    '<div>'
    '<p style="font-size:1.1rem; font-weight:600; margin:0; color:#e5e7f0;">'
    'Habla con <span style="color:#8b5cf6;">Odd Worlds</span></p>'
    '<p style="color:#7b86a8; font-size:0.78rem; margin:0.3rem auto 0; '
    'max-width:22rem; line-height:1.4;">'
    'Pregunta sobre exoplanetas confirmados, como se detectan, '
    'cuales son los mas raros, o pedime un analisis del catalogo.</p>'
    '</div></div>'
)


# ── Interfaz ──

with gr.Blocks(title="Odd Worlds") as app:
    thread_state = gr.State("")

    with gr.Row(elem_classes=["top-bar"]):
        gr.HTML(
            '<div class="app-header">'
            "<h1>Odd Worlds</h1>"
            "<p>Exoplanetas anomalos en el universo</p>"
            "</div>"
        )
        new_btn = gr.Button(
            "+ Nueva conversacion",
            size="sm",
            variant="secondary",
            elem_classes=["new-chat-btn"],
            scale=0,
            min_width=160,
        )

    with gr.Tabs(elem_classes=["main-tabs"]):

        # ── Tab: Agent ──
        with gr.Tab("Agent"):
            chatbot = gr.Chatbot(
                show_label=False,
                label="",
                container=False,
                height="calc(100vh - 180px)",
                elem_classes=["chatbot-area"],
                placeholder=EMPTY_STATE_HTML,
                layout="bubble",
                examples=[
                    {"text": s, "display_text": s}
                    for s in SUGGESTIONS
                ],
            )

            with gr.Row(elem_classes=["input-area"]):
                msg = gr.Textbox(
                    placeholder="Escribi tu pregunta...",
                    show_label=False,
                    scale=9,
                    container=False,
                )
                send_btn = gr.Button(
                    "↑",
                    scale=0,
                    variant="primary",
                    elem_classes=["send-btn"],
                    min_width=44,
                )

            gr.HTML(
                "<p class='disclaimer'>Odd Worlds puede cometer "
                "errores. Datos del NASA Exoplanet Archive.</p>"
            )

        # ── Tab: Dataset ──
        with gr.Tab("Dataset"):
            gr.HTML(
                '<div class="dataset-header">'
                '<span class="count">' + str(len(_display_df)) + "</span> "
                '<span class="label">exoplanetas confirmados del NASA Exoplanet Archive</span>'
                "</div>"
            )
            gr.Dataframe(
                value=_display_df,
                interactive=False,
                wrap=True,
                elem_classes=["dataset-table"],
            )

    # ── Events ──

    outputs = [msg, chatbot, thread_state]

    msg.submit(respond, [msg, chatbot, thread_state], outputs)
    send_btn.click(respond, [msg, chatbot, thread_state], outputs)

    def on_example_select(evt: gr.SelectData, history, thread_id):
        yield from respond(evt.value["text"], history, thread_id)

    chatbot.example_select(
        on_example_select, [chatbot, thread_state], outputs,
    )

    new_btn.click(new_conversation, outputs=outputs)


if __name__ == "__main__":
    app.launch(theme=SPACE_THEME, css=CSS)
