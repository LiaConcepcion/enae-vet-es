"""FastAPI clinic chatbot (v1 parity): Spanish UI, system prompt, conversation memory, POST /ask_bot.

Reads ``OPENAI_API_KEY`` from the environment (Vercel env or local ``.env`` via python-dotenv).
"""

from __future__ import annotations

import os
import threading
from urllib.parse import parse_qs

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

load_dotenv()

SYSTEM_PROMPT_ES = """Eres un asistente virtual de una clínica veterinaria. Cumple SIEMPRE estas reglas:

- Alcance: solo gestionas información y citas relacionadas con ESTERILIZACIÓN / CASTRACIÓN. No ofreces otro tipo de consultas ni servicios en este canal.
- Perros — entrega (drop-off): de 8:00 a 9:00; recogida (pick-up): de 16:00 a 18:00.
- Gatos — entrega: de 8:00 a 9:00; recogida: aproximadamente a las 15:00. Deben venir en transportín rígido (no cartón ni tela).
- Capacidad quirúrgica diaria: como máximo 240 minutos de cirugía en total por día.
- Si una perra está en celo, la cirugía debe posponerse 2 meses.
- Ayuno preoperatorio: 8–12 horas sin comida; agua permitida hasta 1–2 horas antes de la cirugía.
- Analítica preoperatoria (sangre) obligatoria en animales de más de 6 años.
- Si el cliente tiene MÁS DE UN animal / varias mascotas, indícale que debe llamar por teléfono a la clínica (no gestiones varias mascotas aquí).
- Urgencias o cualquier tema fuera de este alcance: deriva al personal de la clínica (teléfono o contacto humano); no inventes citas ni diagnósticos.
- Recuerda y utiliza lo que el cliente te diga a lo largo del chat (especie, nombre del paciente, datos relevantes) para responder de forma coherente.

No diagnostiques ni prescribas medicamentos. Sé claro, profesional y responde en español salvo que el cliente pida otro idioma."""

CHAT_HTML_ES = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"><title>Asistente — Clínica veterinaria</title>
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
    <header class="msger-header">Asistente — Esterilización / castración (memoria de conversación)</header>
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
      var k = "enae_chat_session_fastapi";
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
          var err = (xhr.responseJSON && xhr.responseJSON.detail) ? xhr.responseJSON.detail : xhr.statusText;
          $(".msger-chat").append('<div class="msg left-msg"><div class="msg-bubble">Error: ' + err + '</div></div>');
        });
      });
    })();
  </script>
</body>
</html>
"""

app = FastAPI(
    title="Chatbot clínica",
    version="1.0.0",
    description="API FastAPI: chat en español con memoria (LangChain), compatible con Vercel.",
)

_session_lock = threading.Lock()
_session_histories: dict[str, list[dict]] = {}


class AskBotResponse(BaseModel):
    """Bot reply and echo of ``session_id`` for the client."""

    msg: str = Field(examples=["Respuesta del asistente."])
    session_id: str = Field(examples=["s1"])


@app.get(
    "/",
    summary="Home",
    response_class=Response,
    responses={200: {"content": {"text/html": {}}}},
)
async def home() -> Response:
    return Response(content=CHAT_HTML_ES, media_type="text/html; charset=utf-8")


def _parse_urlencoded_body(body_bytes: bytes) -> dict[str, str]:
    parsed = parse_qs(body_bytes.decode("utf-8"), keep_blank_values=True)
    flat: dict[str, str] = {}
    for key, values in parsed.items():
        if values:
            flat[key] = values[-1]
    return flat


def _validate_ask_bot_fields(msg: str | None, session_id: str | None) -> tuple[str, str]:
    if msg is None or session_id is None:
        raise HTTPException(
            status_code=422,
            detail="msg y session_id son obligatorios",
        )
    msg_clean = msg.strip()
    session_clean = session_id.strip()
    if not msg_clean or not session_clean:
        raise HTTPException(
            status_code=422,
            detail="msg y session_id deben ser cadenas no vacías",
        )
    return msg_clean, session_clean


@app.post(
    "/ask_bot",
    summary="Ask Bot",
    response_model=AskBotResponse,
)
async def ask_bot(request: Request) -> AskBotResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/x-www-form-urlencoded" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Content-Type debe ser application/x-www-form-urlencoded",
        )
    body_bytes = await request.body()
    if not body_bytes.strip():
        raise HTTPException(status_code=422, detail="El cuerpo de la petición está vacío")
    fields = _parse_urlencoded_body(body_bytes)
    msg, session_id = _validate_ask_bot_fields(
        fields.get("msg"),
        fields.get("session_id"),
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return AskBotResponse(
            msg=(
                "OPENAI_API_KEY no está configurada. "
                "Define la variable en Vercel o en el archivo .env local."
            ),
            session_id=session_id,
        )

    with _session_lock:
        if session_id not in _session_histories:
            _session_histories[session_id] = []
        history = list(_session_histories[session_id])

    messages = [{"role": "system", "content": SYSTEM_PROMPT_ES}] + history + [{"role": "user", "content": msg}]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "temperature": 0.3, "messages": messages},
            )
            resp.raise_for_status()
            bot_msg = resp.json()["choices"][0]["message"]["content"]

        with _session_lock:
            _session_histories[session_id].append({"role": "user", "content": msg})
            _session_histories[session_id].append({"role": "assistant", "content": bot_msg})

        return AskBotResponse(msg=bot_msg, session_id=session_id)
    except Exception as e:  # noqa: BLE001
        return AskBotResponse(msg=f"Error: {e}", session_id=session_id)
