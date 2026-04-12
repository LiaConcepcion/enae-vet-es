"""Chatbot v1 — veterinary clinic assistant with Spanish system rules and conversation memory.

Flask on port 5000. Set OPENAI_API_KEY in .env. Each browser tab/session uses ``session_id`` for memory.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

load_dotenv()

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

No diagnostiques ni prescribas medicamentos. Sé claro, profesional y responde en español salvo que el cliente pida otro idioma."""

html = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"><title>Chatbot v1</title>
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
    <header class="msger-header">Chatbot v1 — Clínica (esterilización, memoria de conversación)</header>
    <main class="msger-chat">
      <div class="msg left-msg"><div class="msg-bubble">Hola. Soy el asistente de la clínica para esterilización/castración. ¿En qué puedo ayudarte?</div></div>
    </main>
    <form class="msger-inputarea">
      <input type="text" class="msger-input" id="textInput" placeholder="Escribe tu mensaje...">
      <button type="submit" class="msger-send-btn">Enviar</button>
    </form>
  </section>
  <script>
    (function() {
      var k = "enae_chat_session_v1";
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


def _get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    with _session_lock:
        if session_id not in _session_histories:
            _session_histories[session_id] = InMemoryChatMessageHistory()
        return _session_histories[session_id]


def _build_chain_with_history() -> RunnableWithMessageHistory | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_ES),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    base = prompt | llm
    return RunnableWithMessageHistory(
        base,
        _get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )


_chain_with_history = _build_chain_with_history()


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
    if _chain_with_history is None:
        return jsonify({"msg": "OPENAI_API_KEY no está configurada. Añádela en .env y reinicia."})
    try:
        config = {"configurable": {"session_id": session_id}}
        response = _chain_with_history.invoke({"input": user_msg}, config=config)
        bot_msg = response.content if hasattr(response, "content") else str(response)
        return jsonify({"msg": bot_msg})
    except Exception as e:  # noqa: BLE001
        return jsonify({"msg": "Error: " + str(e)})


if __name__ == "__main__":
    print("Chatbot v1 — http://127.0.0.1:5000/ (stop with Ctrl+C)")
    app.run(host="127.0.0.1", port=5000, debug=False)
