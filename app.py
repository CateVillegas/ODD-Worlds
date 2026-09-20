"""Interfaz web de Odd Worlds."""

from __future__ import annotations

import os
import sqlite3
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
    "pl_rade": "Radio (R tierra)",
    "pl_bmasse": "Masa (M tierra)",
    "pl_eqt": "T eq (K)",
    "pl_orbper": "Periodo (dias)",
    "pl_dens": "Densidad (g/cm3)",
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


def _thread_choices() -> list[str]:
    if not _threads:
        return []
    return [f"{info['title']}  |  {info['created']}"
            for _, info in reversed(list(_threads.items()))]


def _tid_from_label(label: str) -> str | None:
    for tid, info in reversed(list(_threads.items())):
        check = f"{info['title']}  |  {info['created']}"
        if check == label:
            return tid
    return None


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

    return bubbles[:4] if bubbles else [text.strip()]


def respond(message: str, history: list[dict], thread_id: str):
    if not message or not message.strip():
        yield "", history, thread_id, gr.update()
        return

    if not thread_id or thread_id not in _threads:
        thread_id = _new_thread()

    history = history + [{"role": "user", "content": message}]
    history_typing = history + [{"role": "assistant", "content": "..."}]
    yield "", history_typing, thread_id, gr.update()

    try:
        result = _graph.invoke(
            {"question": message, "trace": []},
            config={"configurable": {"thread_id": thread_id}},
        )
        answer = result.get("answer", "No pude generar una respuesta.")
    except Exception:
        answer = "Hubo un error procesando tu pregunta. Proba de nuevo."

    if _threads[thread_id]["title"] == "Nueva conversacion":
        _threads[thread_id]["title"] = message[:30]

    history_clean = [m for m in history if m.get("content") != "..."]
    bubbles = _split_bubbles(answer)

    for bubble in bubbles:
        history_clean = history_clean + [{"role": "assistant", "content": bubble}]

    yield "", history_clean, thread_id, gr.update(choices=_thread_choices())


def _make_suggestion_handler(text: str):
    def handler(history, thread_id):
        yield from respond(text, history, thread_id)
    return handler


def new_conversation():
    tid = _new_thread()
    return [], tid, gr.update(choices=_thread_choices())


def switch_conversation(choice: str):
    if not choice:
        return gr.update(), gr.update()
    tid = _tid_from_label(choice)
    if tid:
        return [], tid
    return gr.update(), gr.update()


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

/* ── Header ── */
.app-header { text-align: center; padding: 0.4rem 0 0.1rem; flex-shrink: 0; }
.app-header h1 {
    font-size: 1.25rem; font-weight: 700;
    background: linear-gradient(135deg, #8b5cf6, #a78bfa, #c4b5fd);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0;
}
.app-header p { color: #7b86a8; font-size: 0.68rem; margin: 0.1rem 0 0; }

/* ── Tabs ── */
.main-tabs { flex: 1 !important; min-height: 0 !important; overflow: hidden !important; }
.main-tabs > .tab-nav { flex-shrink: 0 !important; }
.main-tabs > .tabitem {
    flex: 1 !important; min-height: 0 !important; overflow: hidden !important;
}

/* ── Agent tab main row ── */
.main-row { flex: 1 !important; min-height: 0 !important; overflow: hidden !important; }

/* ── Sidebar ── */
.sidebar-col {
    background: rgba(19,24,45,0.8) !important;
    border: 1px solid #2a3250 !important;
    border-radius: 16px !important; padding: 0.8rem !important;
    max-width: 200px !important; flex: 0 0 180px !important;
    backdrop-filter: blur(12px) !important;
}

/* ── Chat column ── */
.chat-column {
    flex: 1 !important; min-height: 0 !important;
    display: flex !important; flex-direction: column !important;
    overflow: hidden !important;
}

/* ── Chatbot: max-height prevents overflow ── */
.chatbot-area {
    border-radius: 12px !important; overflow: hidden !important;
    max-height: calc(100vh - 310px) !important;
}

/* ── Bubbles ── */
.chatbot-area .bot { border-radius: 18px 18px 18px 4px !important; }
.chatbot-area .user { border-radius: 18px 18px 4px 18px !important; }

/* ── Hide Gradio chrome ── */
.chatbot-area .icon-button-wrapper,
.chatbot-area .message-buttons-right,
.chatbot-area .message-buttons-left { display: none !important; }
footer { display: none !important; }

/* ── Suggestions ── */
.sug-row {
    flex-wrap: wrap !important; gap: 8px !important;
    justify-content: center !important;
    padding: 0.3rem 0.5rem !important; flex-shrink: 0 !important;
    max-width: 36rem !important; margin: 0 auto !important;
}
.sug-btn {
    flex: 0 1 calc(50% - 4px) !important;
    border-radius: 12px !important; font-size: 0.75rem !important;
    padding: 0.45rem 0.7rem !important;
    min-height: unset !important; height: auto !important;
    text-align: left !important;
    background: rgba(19,24,45,0.6) !important;
    border: 1px solid rgba(42,50,80,0.7) !important;
    color: rgba(229,231,240,0.85) !important;
    transition: border-color 0.2s, background 0.2s !important;
    white-space: normal !important; line-height: 1.3 !important;
}
.sug-btn:hover {
    border-color: rgba(139,92,246,0.4) !important;
    background: rgba(19,24,45,0.95) !important;
}

/* ── Input ── */
.input-area {
    flex-shrink: 0 !important; gap: 8px !important;
    align-items: flex-end !important; padding: 0.3rem 0 !important;
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

/* ── New chat ── */
.new-chat-btn { border-radius: 16px !important; width: 100% !important; }

/* ── Animations ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
.chatbot-area .message-row { animation: fadeUp 0.25s ease-out !important; }

/* ── Links ── */
.chatbot-area a { color: #a78bfa !important; }
.chatbot-area em { color: #a78bfa !important; }

/* ── Sidebar internals ── */
.sidebar-col .wrap { background: transparent !important; }

/* ── Disclaimer ── */
.disclaimer {
    color: #7b86a8 !important; font-size: 0.6rem !important;
    text-align: center !important; padding: 0.1rem 0 !important;
    margin: 0 !important;
}

/* ── Dataset tab ── */
.dataset-info {
    color: #7b86a8; font-size: 0.8rem; text-align: center;
    padding: 0.3rem 0;
}
.dataset-info span { color: #8b5cf6; font-weight: 600; }
"""


EMPTY_STATE_HTML = (
    '<div style="display:flex; flex-direction:column; align-items:center; '
    'gap:1rem; padding:2rem 1rem; text-align:center;">'
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
    'max-width:20rem; line-height:1.4;">'
    'Pregunta sobre exoplanetas confirmados, como se detectan '
    'y cuales son los mas raros.</p>'
    '</div></div>'
)


# ── Interfaz ──

with gr.Blocks(title="Odd Worlds") as app:
    thread_state = gr.State("")

    gr.HTML(
        '<div class="app-header">'
        "<h1>Odd Worlds</h1>"
        "<p>Exoplanetas anomalos en el universo</p>"
        "</div>"
    )

    with gr.Tabs(elem_classes=["main-tabs"]):

        # ── Tab: Agent ──
        with gr.Tab("Agent"):
            with gr.Row(elem_classes=["main-row"]):
                with gr.Column(
                    scale=1, min_width=160, elem_classes=["sidebar-col"]
                ):
                    new_btn = gr.Button(
                        "Nueva conversacion",
                        variant="primary",
                        elem_classes=["new-chat-btn"],
                    )
                    gr.HTML(
                        "<p style='color:#7b86a8; font-size:0.7rem; "
                        "margin:0.5rem 0 0.2rem'>Historial</p>"
                    )
                    thread_dropdown = gr.Dropdown(
                        choices=_thread_choices(),
                        interactive=True,
                        show_label=False,
                    )

                with gr.Column(scale=6, elem_classes=["chat-column"]):
                    chatbot = gr.Chatbot(
                        show_label=False,
                        elem_classes=["chatbot-area"],
                        placeholder=EMPTY_STATE_HTML,
                    )

                    with gr.Row(elem_classes=["sug-row"]):
                        sug_btns = []
                        for s in SUGGESTIONS:
                            sug_btns.append(
                                gr.Button(
                                    s,
                                    size="sm",
                                    variant="secondary",
                                    elem_classes=["sug-btn"],
                                )
                            )

                    with gr.Row(elem_classes=["input-area"]):
                        msg = gr.Textbox(
                            placeholder="Escribi tu pregunta...",
                            show_label=False,
                            scale=9,
                            container=False,
                        )
                        send_btn = gr.Button(
                            "^",
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
                '<p class="dataset-info">'
                "<span>" + str(len(_display_df)) + "</span>"
                " exoplanetas confirmados del NASA Exoplanet Archive"
                "</p>"
            )
            gr.Dataframe(
                value=_display_df,
                interactive=False,
                wrap=True,
            )

    # ── Events ──

    outputs = [msg, chatbot, thread_state, thread_dropdown]
    msg.submit(respond, [msg, chatbot, thread_state], outputs)
    send_btn.click(respond, [msg, chatbot, thread_state], outputs)
    for i, btn in enumerate(sug_btns):
        btn.click(
            _make_suggestion_handler(SUGGESTIONS[i]),
            [chatbot, thread_state],
            outputs,
        )
    new_btn.click(
        new_conversation,
        outputs=[chatbot, thread_state, thread_dropdown],
    )
    thread_dropdown.change(
        switch_conversation,
        [thread_dropdown],
        [chatbot, thread_state],
    )


if __name__ == "__main__":
    app.launch(theme=SPACE_THEME, css=CSS)
