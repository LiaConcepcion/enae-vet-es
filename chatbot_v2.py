"""Chatbot v2 — igual que v1 + RAG (FAISS) sobre instrucciones preoperatorias.

Indexa el contenido de la URL indicada; si la página es SPA y el HTML trae poco texto,
se usa el espejo en ``data/rag/instructions-before-operation.en.txt`` (mismo origen público).

Puerto 5000 (Flask). ``OPENAI_API_KEY`` en el entorno o ``.env``.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RAG_SOURCE_URL = (
    "https://veterinary-clinic-teal.vercel.app/en/docs/instructions-before-operation"
)
MIN_LIVE_TEXT_CHARS = 400

SYSTEM_PROMPT_ES = """Eres un asistente virtual de una clínica veterinaria. Cumple SIEMPRE estas reglas:

- Alcance: solo gestionas información y citas relacionadas con ESTERILIZACIÓN / CASTRACIÓN. No ofreces otro tipo de consultas ni servicios en este canal.
- Perros — entrega (drop-off): de 9:00 a 10:30; recogida (pick-up): aproximadamente a las 12:00.
- Gatos — entrega: de 8:00 a 9:00; recogida: aproximadamente a las 15:00. Deben venir en transportín rígido (no cartón ni tela).
- Capacidad quirúrgica diaria: como máximo 240 minutos de cirugía en total por día.
- Si una perra está en celo, la cirugía debe posponerse 2 meses.
- Ayuno preoperatorio: 8–12 horas sin comida; agua permitida hasta 1–2 horas antes de la cirugía.
- Analítica preoperatoria (sangre) obligatoria en animales de más de 6 años.
- Si el cliente tiene MÁS DE UN animal / varias mascotas, indícale que debe llamar por teléfono a la clínica (no gestiones varias mascotas aquí).
- Urgencias o cualquier tema fuera de este alcance: deriva al personal de la clínica (teléfono o contacto humano); no inventes citas ni diagnósticos.
- Recuerda y utiliza lo que el cliente te diga a lo largo del chat (especie, nombre del paciente, datos relevantes) para responder de forma coherente.

Para preguntas sobre instrucciones preoperatorias, ayuno, preparación, consentimiento, día de la operación o cuidados inmediatos descritos en la documentación del centro, integra el contexto recuperado abajo con estas reglas (si hubiera contradicción menor en horarios operativos, prioriza las reglas fijas de este mensaje).

No diagnostiques ni prescribas medicamentos. Sé claro, profesional y responde en español salvo que el cliente pida otro idioma.

--- Fragmentos recuperados de la documentación (inglés; explica al cliente en español) ---
{context}
--- Fin del contexto ---"""

html = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"><title>Chatbot v2</title>
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
    <header class="msger-header">Chatbot v2 — Clínica + RAG (instrucciones preoperatorias)</header>
    <main class="msger-chat">
      <div class="msg left-msg"><div class="msg-bubble">Hola. Soy el asistente de la clínica para esterilización/castración. Puedo ayudarte con preparación y ayuno usando la documentación del centro. ¿En qué puedo ayudarte?</div></div>
    </main>
    <form class="msger-inputarea">
      <input type="text" class="msger-input" id="textInput" placeholder="Escribe tu mensaje...">
      <button type="submit" class="msger-send-btn">Enviar</button>
    </form>
  </section>
  <script>
    (function() {
      var k = "enae_chat_session_v2";
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

_chain_with_history: RunnableWithMessageHistory | None = None
_rag_bootstrap_error: str | None = None
_rag_init_lock = threading.Lock()


def _get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    with _session_lock:
        if session_id not in _session_histories:
            _session_histories[session_id] = InMemoryChatMessageHistory()
        return _session_histories[session_id]


def _fallback_mirror_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "rag" / "instructions-before-operation.en.txt"


def load_instruction_documents(url: str) -> list[Document]:
    """Load docs from the public URL; use bundled mirror if the site is client-rendered."""
    loader = WebBaseLoader(
        url,
        requests_kwargs={
            "timeout": 45,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; enae-vet-es-rag/2.0; veterinary-course-bot)"
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
        "RAG: live URL returned only %s chars (typical SPA shell); using mirror %s",
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


def _build_rag_chain() -> RunnableWithMessageHistory:
    docs = load_instruction_documents(RAG_SOURCE_URL)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(splits, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    def inject_context(payload: dict[str, Any]) -> dict[str, Any]:
        question = payload["input"]
        history = payload.get("chat_history") or []
        retrieved = retriever.invoke(question)
        context = _format_context(retrieved)
        return {
            "input": question,
            "chat_history": history,
            "context": context,
        }

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_ES),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    rag_runnable = RunnableLambda(inject_context) | prompt | llm
    return RunnableWithMessageHistory(
        rag_runnable,
        _get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )


def _ensure_chain() -> RunnableWithMessageHistory | None:
    global _chain_with_history, _rag_bootstrap_error
    if _chain_with_history is not None:
        return _chain_with_history
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    with _rag_init_lock:
        if _chain_with_history is not None:
            return _chain_with_history
        if _rag_bootstrap_error is not None:
            return None
        try:
            _chain_with_history = _build_rag_chain()
        except Exception as e:  # noqa: BLE001
            logger.exception("RAG bootstrap failed")
            _rag_bootstrap_error = str(e)
            return None
        return _chain_with_history


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

    chain = _ensure_chain()
    if chain is None and _rag_bootstrap_error:
        return jsonify(
            {"msg": f"No se pudo inicializar RAG: {_rag_bootstrap_error}"},
        )
    if chain is None:
        return jsonify({"msg": "No se pudo cargar el modelo. Revisa la configuración."})

    try:
        config = {"configurable": {"session_id": session_id}}
        response = chain.invoke({"input": user_msg}, config=config)
        bot_msg = response.content if hasattr(response, "content") else str(response)
        return jsonify({"msg": bot_msg})
    except Exception as e:  # noqa: BLE001
        return jsonify({"msg": "Error: " + str(e)})


if __name__ == "__main__":
    print("Chatbot v2 — http://127.0.0.1:5000/ (stop with Ctrl+C)")
    app.run(host="127.0.0.1", port=5001, debug=False)
