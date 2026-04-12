"""Chatbot v0 — simplest pipeline: user message → LLM → reply (no memory, no system prompt).

Matches the course notebook flow (Flask on port 5000). Set OPENAI_API_KEY in .env or the environment.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><title>Chatbot v0</title>
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
    <header class="msger-header">Chatbot v0 — No memory, no system prompt</header>
    <main class="msger-chat">
      <div class="msg left-msg"><div class="msg-bubble">Hi! I have no memory and no instructions. Send a message.</div></div>
    </main>
    <form class="msger-inputarea">
      <input type="text" class="msger-input" id="textInput" placeholder="Enter your message...">
      <button type="submit" class="msger-send-btn">Send</button>
    </form>
  </section>
  <script>
    $(".msger-inputarea").on("submit", function(e) {
      e.preventDefault();
      var msgText = $("#textInput").val().trim();
      if (!msgText) return;
      $(".msger-chat").append('<div class="msg right-msg"><div class="msg-bubble">' + $("<div>").text(msgText).html() + '</div></div>');
      $("#textInput").val("");
      $.post("/ask_bot", { msg: msgText }).done(function(data) {
        $(".msger-chat").append('<div class="msg left-msg"><div class="msg-bubble">' + $("<div>").text(data.msg || data).html() + '</div></div>');
      }).fail(function(xhr) { $(".msger-chat").append('<div class="msg left-msg"><div class="msg-bubble">Error: ' + (xhr.responseJSON && xhr.responseJSON.msg ? xhr.responseJSON.msg : xhr.statusText) + '</div></div>'); });
    });
  </script>
</body>
</html>
"""

app = Flask(__name__)


def _get_bot_chain():
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return prompt | llm


_bot_chain = _get_bot_chain()


@app.route("/")
def home() -> str:
    return render_template_string(html)


@app.route("/ask_bot", methods=["POST"])
def ask_bot():
    data = request.form
    user_msg = (data.get("msg") or "").strip()
    if not user_msg:
        return jsonify({"msg": "Please send a non-empty message."})
    if _bot_chain is None:
        return jsonify({"msg": "OPENAI_API_KEY is not set. Add it to .env and restart."})
    try:
        response = _bot_chain.invoke({"input": user_msg})
        bot_msg = response.content if hasattr(response, "content") else str(response)
        return jsonify({"msg": bot_msg})
    except Exception as e:  # noqa: BLE001 — surface LLM/network errors to the UI
        return jsonify({"msg": "Error: " + str(e)})


if __name__ == "__main__":
    print("Chatbot v0 — http://127.0.0.1:5000/ (stop with Ctrl+C)")
    app.run(host="127.0.0.1", port=5000, debug=False)
