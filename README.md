# enae-vet-es

Veterinary clinic chatbot and booking assistant (ENAE case study). This document gives new developers and stakeholders a single entry point to understand the tech stack, the main workflow, and how it relates to the docs in `docs/`.

---

## Proyecto y Gestión

- **Tablero Jira:** [https://liacconcepcion-1776021076256.atlassian.net/jira/software/projects/SCRUM/boards/1](https://liacconcepcion-1776021076256.atlassian.net/jira/software/projects/SCRUM/boards/1)
- **Repositorio GitHub:** [https://github.com/LiaConcepcion/enae-vet-es](https://github.com/LiaConcepcion/enae-vet-es)
- **Alumna:** Lia Concepcion
- **Curso:** Data Science e IA para la Toma de Decisiones — ENAE Business School

---

## Cómo ejecutar

Demos locales en **Flask** (`chatbot_v0.py` y `chatbot_v1.py`). Ambas usan el puerto **5000**; ejecuta **solo una** a la vez. Necesitas una clave **OpenAI** en `.env` (copia `.env.example` a `.env` y define `OPENAI_API_KEY`).

### Entorno (una vez)

```bash
cd /ruta/a/enae-vet-es
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # si aún no existe
# Edita .env y pega tu OPENAI_API_KEY
```

### Chatbot v0

```bash
source .venv/bin/activate
python chatbot_v0.py
```

Abre en el navegador **http://127.0.0.1:5000/**. Detén el servidor con `Ctrl+C` en la terminal.

### Chatbot v1

```bash
source .venv/bin/activate
python chatbot_v1.py
```

Abre **http://127.0.0.1:5000/**. La interfaz envía `session_id` para la memoria de conversación. Detén con `Ctrl+C`.

---

## Technologies

The project uses (or is designed to use) the following technologies. Their roles are summarised here; see `.cursor/skills/langchain-vet-chatbots/SKILL.md` and `.cursor/agents/backend-langchain-vet.md` for implementation guidance.

| Technology | Role |
|------------|------|
| **Python** | Backend language; services, APIs, and LangChain chains/agents. |
| **LangChain** | Orchestration and conversation: system prompts, tools (e.g. appointments, patient lookup), RAG over clinic protocols, and conversation memory. |
| **FastAPI** | HTTP backend and API layer for the bot and any REST endpoints. |
| **Session store** | Conversation and session handling (e.g. per-client or per-session state). |
| **Frontend / channel** | User-facing channel for the bot (e.g. web chat, WhatsApp); exact choice depends on implementation. |

The bot does not diagnose or prescribe; it supports scheduling, FAQs, and internal procedures, and cites tools or retrieved documents when giving procedural information.

---

## Local demos: Chatbot v0 and v1 (Flask)

Two standalone scripts run a small **Flask** app on **http://127.0.0.1:5000** (run **one at a time**; both bind to the same port). Configure **`OPENAI_API_KEY`** in `.env` (see `.env.example`).

| Script | What it does |
|--------|----------------|
| **`chatbot_v0.py`** | Minimal LangChain pipeline: **no system prompt**, **no memory**. Each message is independent. `POST /ask_bot` accepts form field **`msg`** only. |
| **`chatbot_v1.py`** | **Spanish system prompt** with clinic rules for **sterilisation/castration only** (drop-off/pick-up windows by species, 240-minute daily surgery quota, heat postponement, fasting, pre-op blood work over 6 years, multi-pet and out-of-scope redirection). Uses **`RunnableWithMessageHistory`** so the model **remembers the thread** (species, pet name, etc.). `POST /ask_bot` expects **`msg`** and **`session_id`**; the UI stores `session_id` in `localStorage`. |

Para instalar dependencias y arrancar cada script, sigue la sección **[Cómo ejecutar](#cómo-ejecutar)**.

---

## Workflow

The main flow from conversation to confirmed appointment is as follows.

1. **Conversation → intent and slot filling**  
   The user talks to the bot; the bot identifies intent and collects required slots (e.g. species, date, client/patient details).

2. **Day-only selection**  
   The user selects a **day** for the appointment. The bot does **not** ask the user to choose a specific surgical time; times are managed internally.

3. **Capacity rules**  
   - **240-minute quota**: Total minutes already occupied on the day plus the new appointment’s duration must not exceed 240 minutes.  
   - **Dog limit**: A maximum number of dogs per day is enforced (see business rules in `docs/` when available).  
   - **Service times**: Procedure durations and service times come from the master table / business configuration.

4. **Species-specific drop-off windows**  
   - **Cats**: drop-off window 08:00–09:00.  
   - **Dogs**: drop-off window 09:00–10:30.  
   The bot uses these windows for messaging and instructions; surgical times are not shown to the client.

5. **Confirmation**  
   On confirmation, the client receives:  
   - Drop-off instructions (time window and any species-specific guidance).  
   - Fasting protocol (e.g. last meal 8–12 hours before; water until 1–2 hours before, as per clinic policy).  
   Surgical times remain internal; the communication protocol is to emphasise drop-off and fasting, not specific surgery slots.

---

## Docs overview

Documentation in `docs/` is the single source of truth for business rules, scheduling logic, and pre-surgery considerations. The README stays aligned with these files.

| Document | Contents | When to use it |
|----------|----------|----------------|
| **`docs/pre-operative-considerations.md`** | Clinic profile (preventive care, sterilisation, vaccinations, no routine consultations or emergencies), pre-surgery instructions (fasting, transport, consent, pick-up times), and post-op care. Language: Spanish. | Understanding clinic scope, pre-op and post-op instructions, and client-facing messaging (e.g. RAG or confirmation text). |
| **Business rules / scheduling** | When present in `docs/` (e.g. `business-rules.md`), quota rules, service times, dog limit, drop-off windows, and communication protocol. | Implementing or verifying booking logic, capacity checks, and messaging rules. |
| **`docs/jira/`** | Groomed Jira exports: enriched ticket specs and before/after examples (e.g. `VETES-14-enriched.md`). | Tracing backlog decisions and onboarding to the **enrich** workflow. |
| **[`docs/intents-catalog.md`](docs/intents-catalog.md)** | Catálogo de 20 intenciones del chatbot (saludo, agenda, disponibilidad, preoperatorio, ayuno, horarios, especies, derivaciones, etc.) con ejemplos en español. | Diseño de NLU, pruebas conversacionales y alineación de prompts. |

If you add new docs (e.g. `business-rules.md`, `considerations.md`), add a row here and keep the README consistent with them.

---

## Consistency

The README is written so that:

- **Quota and capacity**: The 240-minute rule and dog limit described in the Workflow section match the rules in `docs/` (and in any `.cursor/rules` that encode them).  
- **Service and drop-off times**: Species-specific drop-off windows (cats 08:00–09:00, dogs 09:00–10:30) and the use of a master table for service times align with the docs.  
- **Communication protocol**: Hiding surgical times and showing drop-off and fasting on confirmation is consistent with `docs/pre-operative-considerations.md` and any business-rules or considerations docs in `docs/`.

When you change business rules or scheduling logic in `docs/`, update this README so there are no contradictions.

---

## API (FastAPI — mismo comportamiento que `chatbot_v1.py`)

La API en `main.py` expone el mismo asistente (prompt del sistema en español, reglas de la clínica, memoria por `session_id` vía LangChain). Lee **`OPENAI_API_KEY`** del entorno (Vercel o `.env` local).

- **GET /**: interfaz de chat en español (jQuery → `POST /ask_bot`).
- **POST /ask_bot**: cuerpo `application/x-www-form-urlencoded` con **`msg`** y **`session_id`**. Respuesta JSON: `{"msg": "...", "session_id": "..."}`.

### Run the API

```bash
# Create venv and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Start uvicorn
.venv/bin/uvicorn main:app --reload
```

Then:

- Interactive docs: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json

### Example requests

```bash
# GET home
curl http://127.0.0.1:8000/

# POST ask_bot (urlencoded)
curl -X POST http://127.0.0.1:8000/ask_bot \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "msg=hello&session_id=s1"
```

Example response (texto real depende del modelo y del historial):

```json
{"msg": "…", "session_id": "s1"}
```

Si falta `OPENAI_API_KEY`, `msg` indica que debes configurarla.

---

## Cursor workflows

- **Implement a Jira ticket**: Say *"Implement PROJ-123"* (or *@implement-jira-workflow implement PROJ-123*). The agent will read the ticket, plan from AC, ask questions if needed, develop using the **backend-langchain-vet** subagent, move the ticket to In Progress, open a PR with an AC-based description, and move the ticket to In Review. Full steps: [.cursor/commands/implement.md](.cursor/commands/implement.md).

- **Enrich / groom a Jira ticket**: Say *"Enrich VETES-1"* or *"/enrich PROJ-123"*. The agent loads the issue, refines it in phases (diagnosis, structure, acceptance criteria, delivery readiness) using the **product-manager** agent and **product-manager-ticket-enrichment** skill, then consolidates an artifact; publishing back to Jira requires your explicit approval. Example output: [`docs/jira/VETES-14-before-after-example.md`](docs/jira/VETES-14-before-after-example.md). Full steps: [.cursor/commands/enrich.md](.cursor/commands/enrich.md).
