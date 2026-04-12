"""Chatbot v3 — v2 + herramienta ``check_availability`` (mock) con RAG y memoria.

Puerto 5000 (Flask). ``OPENAI_API_KEY`` en el entorno o ``.env``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RAG_SOURCE_URL = (
    "https://veterinary-clinic-teal.vercel.app/en/docs/instructions-before-operation"
)
MIN_LIVE_TEXT_CHARS = 400

DOG_MINUTES = 90
CAT_MINUTES = 60
DAY_CAP_MINUTES = 240
MAX_DOGS_PER_DAY = 2

SYSTEM_PROMPT_ES = """Eres un asistente virtual de una clínica veterinaria. Cumple SIEMPRE estas reglas:

- Alcance: solo gestionas información y citas relacionadas con ESTERILIZACIÓN / CASTRACIÓN. No ofreces otro tipo de consultas ni servicios en este canal.
- Perros — entrega (drop-off): de 8:00 a 9:00; recogida (pick-up): de 16:00 a 18:00.
- Gatos — entrega: de 8:00 a 9:00; recogida: después de las 17:00. Deben venir en transportín rígido (no cartón ni tela).
- Capacidad quirúrgica diaria: como máximo 240 minutos de cirugía en total por día.
- Si una perra está en celo, la cirugía debe posponerse 2 meses.
- Ayuno preoperatorio: 8–12 horas sin comida; agua permitida hasta 1–2 horas antes de la cirugía.
- Analítica preoperatoria (sangre) obligatoria en animales de más de 6 años.
- Si el cliente tiene MÁS DE UN animal / varias mascotas, indícale que debe llamar por teléfono a la clínica (no gestiones varias mascotas aquí).
- Urgencias o cualquier tema fuera de este alcance: deriva al personal de la clínica (teléfono o contacto humano); no inventes citas ni diagnósticos.
- Recuerda y utiliza lo que el cliente te diga a lo largo del chat (especie, nombre del paciente, datos relevantes) para responder de forma coherente.

Herramientas: cuando el usuario pregunte por disponibilidad, huecos o si hay cita para una FECHA concreta con un PERRO o un GATO, debes llamar a la herramienta ``check_availability`` con los argumentos ``date`` (texto de la fecha) y ``species`` (\"dog\" o \"cat\"; también acepta perro/gato). Incorpora el texto que devuelve la herramienta en tu respuesta al cliente.

Para preguntas sobre instrucciones preoperatorias, ayuno, preparación, consentimiento, día de la operación o cuidados inmediatos descritos en la documentación del centro, integra el contexto recuperado abajo con estas reglas (si hubiera contradicción menor en horarios operativos, prioriza las reglas fijas de este mensaje).

No diagnostiques ni prescribas medicamentos. Sé claro, profesional y responde en español salvo que el cliente pida otro idioma.

--- Fragmentos recuperados de la documentación (inglés; explica al cliente en español) ---
{context}
--- Fin del contexto ---"""


def _parse_date_string(raw: str) -> date | None:
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _species_is_dog(species: str) -> bool | None:
    s = species.strip().lower()
    if s in ("dog", "perro", "perros"):
        return True
    if s in ("cat", "gato", "gata", "gatos"):
        return False
    return None


def _mock_bookings_for_day(date_key: str) -> tuple[int, int]:
    """Return (dogs_booked, cats_booked) deterministic mock for that calendar day."""
    h = int(hashlib.sha256(date_key.encode("utf-8")).hexdigest(), 16)
    dogs_booked = min(MAX_DOGS_PER_DAY, h % (MAX_DOGS_PER_DAY + 1))
    cats_booked = (h // 11) % 5
    while dogs_booked * DOG_MINUTES + cats_booked * CAT_MINUTES > DAY_CAP_MINUTES:
        cats_booked -= 1
    if cats_booked < 0:
        cats_booked = 0
    return dogs_booked, cats_booked


def _format_date_es(d: date) -> str:
    months = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    weekdays = (
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    )
    return f"{weekdays[d.weekday()]} {d.day} de {months[d.month - 1]} de {d.year}"


@tool
def check_availability(date: str, species: str) -> str:
    """Consulta disponibilidad quirúrgica (simulada) para una fecha y especie.

    :param date: Fecha en texto (p. ej. 2026-04-15 o 15/04/2026).
    :param species: \"dog\" o \"cat\" (también perro/gato).
    :returns: Mensaje en español con disponibilidad y franjas orientativas.
    """
    d = _parse_date_string(date)
    if d is None:
        return (
            "No pude interpretar la fecha. Indica un día concreto, por ejemplo "
            "2026-05-20 o 20/05/2026."
        )

    if d.weekday() >= 5:
        return (
            f"No hay cirugías programadas el {_format_date_es(d)} (fin de semana). "
            "Elige un día laborable de lunes a viernes."
        )

    kind = _species_is_dog(species)
    if kind is None:
        return 'Indica la especie como \"dog\" o \"cat\" (o perro/gato).'

    dogs_booked, cats_booked = _mock_bookings_for_day(d.isoformat())
    used = dogs_booked * DOG_MINUTES + cats_booked * CAT_MINUTES

    if kind:
        if dogs_booked >= MAX_DOGS_PER_DAY:
            return (
                f"Ese día ({_format_date_es(d)}) ya hay {MAX_DOGS_PER_DAY} cirugías de perros "
                "programadas (máximo permitido). Prueba otra fecha o llama a la clínica."
            )
        if used + DOG_MINUTES > DAY_CAP_MINUTES:
            return (
                f"Ese día ({_format_date_es(d)}) la agenda quirúrgica ya está completa "
                f"en cuanto a minutos (tope {DAY_CAP_MINUTES} min). Prueba otra fecha."
            )
        slots = (
            "Entrega (drop-off) habitual para perros: 08:00–09:00; recogida orientativa "
            "16:00–18:00 (confirmar con recepción)."
        )
        return (
            f"¡Hay disponibilidad para un perro el {_format_date_es(d)}! "
            f"(Simulación: {dogs_booked} perro(s) y {cats_booked} gato(s) ya reservados ese día, "
            f"minutos usados ~{used}/{DAY_CAP_MINUTES}). {slots}"
        )

    if used + CAT_MINUTES > DAY_CAP_MINUTES:
        return (
            f"Ese día ({_format_date_es(d)}) no cabe otra cirugía de gato por el límite de "
            f"{DAY_CAP_MINUTES} minutos. Prueba otra fecha."
        )
    slots = (
        "Entrega (drop-off) habitual para gatos: 08:00–09:00; recogida después de las 17:00; "
        "transportín rígido obligatorio."
    )
    return (
        f"¡Hay disponibilidad para un gato el {_format_date_es(d)}! "
        f"(Simulación: {dogs_booked} perro(s) y {cats_booked} gato(s) ya reservados, "
        f"minutos usados ~{used}/{DAY_CAP_MINUTES}). {slots}"
    )


html = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"><title>Chatbot v3</title>
  <style>
    body{font-family:Helvetica;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:linear-gradient(135deg,#f5f7fa,#c3cfe2)}
    .msger{display:flex;flex-direction:column;width:100%;max-width:600px;height:80vh;border:2px solid #ddd;border-radius:8px;background:#fff;box-shadow:0 8px 16px rgba(0,0,0,.1)}
    .msger-header{padding:12px;text-align:center;border-bottom:2px solid #ddd;background:#eee;color:#333;font-weight:bold}
    .msger-chat{flex:1;overflow-y:auto;padding:12px}
    .msg{display:flex;align-items:flex-end;margin-bottom:10px}
    .msg-bubble{max-width:75%;padding:10px 14px;border-radius:12px}
    .left-msg .msg-bubble{background:#ececec;border-bottom-left-radius:2px}
    .right-msg{flex-direction:row-reverse}
    .right-msg .msg-bubble{background:#579ffb;color:#fff;border-bottom-right-radius:2px}
    .msger-inputarea{display:flex;padding:10px;border-top:2px solid #ddd;background:#eee}
    .msger-input{flex:1;padding:10px;border:none;border-radius:6px;margin-right:8px;font-size:1em}
    .msger-send-btn{padding:10px 20px;border:none;border-radius:6px;background:rgb(0,196,65);color:#fff;font-weight:bold;cursor:pointer}
  </style>
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
  <section class="msger">
    <header class="msger-header">Chatbot v3 — Clínica + RAG + disponibilidad (mock)</header>
    <main class="msger-chat">
      <div class="msg left-msg"><div class="msg-bubble">Hola. Puedo orientarte sobre preparación (RAG), y consultar disponibilidad simulada por fecha y especie. ¿Qué necesitas?</div></div>
    </main>
    <form class="msger-inputarea">
      <input type="text" class="msger-input" id="textInput" placeholder="Escribe tu mensaje...">
      <button type="submit" class="msger-send-btn">Enviar</button>
    </form>
  </section>
  <script>
    (function() {
      var k = "enae_chat_session_v3";
      var sid = localStorage.getItem(k);
      if (!sid) { sid = "sess_" + Math.random().toString(36).slice(2) + "_" + Date.now(); localStorage.setItem(k, sid); }
      $(".msger-inputarea").on("submit", function(e) {
        e.preventDefault();
        var msgText = $("#textInput").val().trim();
        if (!msgText) return;
        $(".msger-chat").append('<div class="msg right-msg"><div class="msg-bubble">' + $("<div>").text(msgText).html() + '</div></div>');
        $("#textInput").val("");
        $.post("/ask_bot", { msg: msgText, session_id: sid }).done(function(data) {
          $(".msger-chat").append('<div class="msg left-msg"><div class="msg-bubble">' + $("<div>").text(data.msg || data).html() + '</div></div>');
        }).fail(function(xhr) {
          var err = (xhr.responseJSON && xhr.responseJSON.msg) ? xhr.responseJSON.msg : xhr.statusText;
          $(".msger-chat").append('<div class="msg left-msg"><div class="msg-bubble">Error: ' + err + '</div></div>');
        });
      });
    })();
  </script>
</body>
</html>
"""

app = Flask(__name__)

_session_lock = threading.Lock()
_session_histories: dict[str, InMemoryChatMessageHistory] = {}

_retriever: Any | None = None
_llm_with_tools: ChatOpenAI | None = None
_rag_bootstrap_error: str | None = None
_rag_init_lock = threading.Lock()
_TOOLS = [check_availability]
_MAX_TOOL_ROUNDS = 6


def _get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    with _session_lock:
        if session_id not in _session_histories:
            _session_histories[session_id] = InMemoryChatMessageHistory()
        return _session_histories[session_id]


def _fallback_mirror_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "rag" / "instructions-before-operation.en.txt"


def load_instruction_documents(url: str) -> list[Document]:
    loader = WebBaseLoader(
        url,
        requests_kwargs={
            "timeout": 45,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; enae-vet-es-rag/3.0; veterinary-course-bot)"
                ),
            },
        },
    )
    docs = loader.load()
    total = sum(len(d.page_content) for d in docs)
    if total >= MIN_LIVE_TEXT_CHARS:
        for d in docs:
            d.metadata.setdefault("source", url)
        logger.info("RAG: using live URL text (%s characters)", total)
        return docs

    mirror = _fallback_mirror_path()
    if not mirror.is_file():
        raise FileNotFoundError(
            f"Live URL returned only {total} chars and mirror file is missing: {mirror}",
        )
    text = mirror.read_text(encoding="utf-8")
    logger.warning(
        "RAG: live URL returned only %s chars; using mirror %s",
        total,
        mirror,
    )
    return [
        Document(
            page_content=text,
            metadata={"source": url, "mirror_file": str(mirror)},
        ),
    ]


def _format_context(docs: list[Document]) -> str:
    return "\n\n".join(d.page_content for d in docs)


def _ensure_rag_retriever() -> Any | None:
    global _retriever, _rag_bootstrap_error
    if _retriever is not None:
        return _retriever
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    with _rag_init_lock:
        if _retriever is not None:
            return _retriever
        if _rag_bootstrap_error is not None:
            return None
        try:
            docs = load_instruction_documents(RAG_SOURCE_URL)
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = splitter.split_documents(docs)
            embeddings = OpenAIEmbeddings()
            vectorstore = FAISS.from_documents(splits, embeddings)
            _retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        except Exception as e:  # noqa: BLE001
            logger.exception("RAG bootstrap failed")
            _rag_bootstrap_error = str(e)
            return None
        return _retriever


def _ensure_llm_with_tools() -> ChatOpenAI | None:
    global _llm_with_tools
    if _llm_with_tools is not None:
        return _llm_with_tools
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    _llm_with_tools = ChatOpenAI(model="gpt-4o-mini", temperature=0.3).bind_tools(_TOOLS)
    return _llm_with_tools


def _run_turn(session_id: str, user_text: str) -> str:
    retriever = _ensure_rag_retriever()
    llm = _ensure_llm_with_tools()
    if retriever is None or llm is None:
        raise RuntimeError("RAG o modelo no inicializado")

    hist = _get_session_history(session_id)
    retrieved = retriever.invoke(user_text)
    context = _format_context(retrieved)
    system_content = SYSTEM_PROMPT_ES.format(context=context)

    messages: list[Any] = [SystemMessage(content=system_content)]
    messages.extend(hist.messages)
    messages.append(HumanMessage(content=user_text))

    rounds = 0
    while rounds < _MAX_TOOL_ROUNDS:
        rounds += 1
        ai = llm.invoke(messages)
        if not getattr(ai, "tool_calls", None):
            final = ai.content or ""
            hist.add_user_message(user_text)
            hist.add_ai_message(final)
            return final

        messages.append(ai)
        for tc in ai.tool_calls:
            name = tc.get("name")
            tid = tc.get("id") or ""
            args = tc.get("args") or {}
            if name == "check_availability":
                out = check_availability.invoke(
                    {"date": args.get("date", ""), "species": args.get("species", "")},
                )
            else:
                out = f"Herramienta desconocida: {name}"
            messages.append(ToolMessage(content=str(out), tool_call_id=tid))

    final = "Demasiadas llamadas a herramientas. Reformula tu pregunta."
    hist.add_user_message(user_text)
    hist.add_ai_message(final)
    return final


@app.route("/")
def home() -> str:
    return render_template_string(html)


@app.route("/ask_bot", methods=["POST"])
def ask_bot() -> Any:
    data = request.form
    user_msg = (data.get("msg") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    if not user_msg:
        return jsonify({"msg": "Envía un mensaje no vacío."})
    if not session_id:
        return jsonify({"msg": "Falta session_id. Recarga la página."}), 422
    if not os.environ.get("OPENAI_API_KEY"):
        return jsonify({"msg": "OPENAI_API_KEY no está configurada. Añádela en .env y reinicia."})

    _ensure_rag_retriever()
    if _rag_bootstrap_error:
        return jsonify({"msg": f"No se pudo inicializar RAG: {_rag_bootstrap_error}"})

    try:
        reply = _run_turn(session_id, user_msg)
        return jsonify({"msg": reply})
    except Exception as e:  # noqa: BLE001
        return jsonify({"msg": "Error: " + str(e)})


if __name__ == "__main__":
    print("Chatbot v3 — http://127.0.0.1:5000/ (stop with Ctrl+C)")
    app.run(host="127.0.0.1", port=5000, debug=False)
