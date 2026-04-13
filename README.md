# enae-vet-es

Veterinary clinic chatbot and booking assistant (ENAE case study). This document gives new developers and stakeholders a single entry point to understand the tech stack, the main workflow, and how it relates to the docs in `docs/`.

---

## Proyecto y Gestión

- **Alumna:** Lia Concepcion
- **Curso:** Data Science e IA para la Toma de Decisiones — ENAE Business School
- **Profesor:** Jaime Marco (GitHub: jmarco111)
- **Tablero Jira:** [https://liacconcepcion-1776021076256.atlassian.net/jira/software/projects/SCRUM/boards/1](https://liacconcepcion-1776021076256.atlassian.net/jira/software/projects/SCRUM/boards/1)
- **Repositorio GitHub:** [https://github.com/LiaConcepcion/enae-vet-es](https://github.com/LiaConcepcion/enae-vet-es)
- **URL pública (Vercel):** [https://enae-vet-es-xi.vercel.app](https://enae-vet-es-xi.vercel.app)

---

## Qué hemos implementado

| Componente | Descripción | Archivo |
|---|---|---|
| ✅ **Chatbot base** | System prompt en español, reglas del dominio veterinario, foco en esterilización/castración | `chatbot_v1.py` |
| ✅ **Memoria de sesión** | Conversación coherente entre turnos sin repetir datos ya dados (`session_id`) | `chatbot_v1.py`, `chatbot_v2.py` |
| ✅ **RAG** | Pipeline FAISS sobre la URL oficial de instrucciones preoperatorias | `chatbot_v2.py` |
| ✅ **Tool disponibilidad** | Mock de disponibilidad con reglas de cupo y Tetris de agenda | `chatbot_v3.py` |
| ✅ **Despliegue Vercel** | URL pública con variables de entorno en el panel (sin secretos en Git) | `main.py` |
| ✅ **Catálogo de intents** | 20 intents documentados con mapeo a conversaciones 1–10 | `docs/intents-catalog.md` |
| ✅ **Jira** | 3 EPICs y 14 tickets (VET-1 a VET-14) con trazabilidad al repo | Tablero Jira |

---

## Cómo ejecutar

Necesitas una clave **OpenAI** en `.env`. Copia `.env.example` a `.env` y define `OPENAI_API_KEY`.

### Entorno (una vez)

```bash
cd enae-vet-es
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env y añade tu OPENAI_API_KEY
```

### Chatbot v2 — Con RAG (recomendado para pruebas base)

```bash
source .venv/bin/activate
python chatbot_v2.py
```

Abre en el navegador: **http://127.0.0.1:5000/**

### Chatbot v3 — Con RAG + Tool de disponibilidad

```bash
source .venv/bin/activate
python chatbot_v3.py
```

Abre en el navegador: **http://127.0.0.1:5000/**

### API FastAPI (Vercel)

```bash
source .venv/bin/activate
uvicorn main:app --reload
```

- Interfaz: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs

---

## RAG — Pipeline y fuente oficial

El pipeline RAG indexa el contenido de la URL oficial del caso:

**Fuente:** `https://veterinary-clinic-teal.vercel.app/en/docs/instructions-before-operation`

**Cómo funciona:**

1. `WebBaseLoader` descarga el HTML de la URL oficial
2. Si la página es SPA y devuelve poco texto (<400 chars), usa el espejo local en `data/rag/instructions-before-operation.en.txt` (mismo contenido, mismo origen)
3. `RecursiveCharacterTextSplitter` trocea el texto (chunk_size=1000, overlap=200)
4. `OpenAIEmbeddings` genera embeddings y los indexa en `FAISS`
5. En cada consulta, el `retriever` recupera los 4 chunks más relevantes (`k=4`)
6. El contexto recuperado se inyecta en el system prompt antes de llamar al LLM

**Evidencia de que el retriever funciona** (log en terminal al arrancar):
```
INFO:faiss.loader:Loading faiss.
INFO:faiss.loader:Successfully loaded faiss.
INFO:root:RAG: using live URL text (XXXX characters)
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"
```

**Conversación de prueba RAG (Conv. 10):**
- Usuario: "¿Cuántas horas tiene que estar mi perro sin comer antes de la operación?"
- Bot: Responde con instrucciones de ayuno (8–12h sin comida, agua hasta 1–2h antes) recuperadas desde la URL oficial

---

## Tool de disponibilidad

La tool `check_availability` (mock) simula la consulta de disponibilidad respetando las reglas del caso:

- Capacidad máxima: **240 minutos** de cirugía por día
- Límite de perros por día
- Ventanas de entrega por especie (gatos 08:00–09:00, perros 09:00–10:30)

**Evidencia (Conv. 8 y 9):**
- Usuario: "¿Hay disponibilidad el próximo martes para castrar a mi perro?"
- Bot invoca la tool → devuelve disponibilidad coherente con las reglas del cupo

---

## Conversaciones de aceptación

Las conversaciones 1–7 (base 5 pt) se superan con `chatbot_v2.py` (sin tool). Las conversaciones 8–9 con `chatbot_v3.py` (con tool).

| Conv. | Tema | Verifica |
|---|---|---|
| 1 | Saludo y alcance | Foco esterilización; rechaza consulta clínica |
| 2 | Ventanas entrega + memoria | Gato 08–09h; Perro 09–10:30h; sin repetir especie |
| 3 | Analítica preoperatoria | Obligatoria en >6 años |
| 4 | Emergencia | Deriva a urgencias; no agenda |
| 5 | Reserva rechazada (celo) | Pospone ~2 meses; sin confirmación falsa |
| 6 | Horarios recogida + memoria | Perro ~12h; Gato ~15h |
| 7 | Derivación a humano | Canal concreto de escalada |
| 8 | Disponibilidad (tool) | Tool invocada; respuesta coherente con cupo |
| 9 | Capacidad/Tetris (tool) | Reglas de 240 min respetadas |
| 10 | Ayuno preoperatorio (RAG) | Recuperado desde URL oficial |

Guiones completos: `docs/conversaciones-aceptacion.md` / material del curso.

---

## Catálogo de intents

20 intents documentados en [`docs/intents-catalog.md`](docs/intents-catalog.md) con descripción, ejemplo y mapeo a las conversaciones 1–10.

---

## Technologies

| Technology | Role |
|---|---|
| **Python** | Backend language |
| **LangChain** | Orchestration: prompts, RAG, memory, tools |
| **FastAPI** | HTTP API layer (Vercel) |
| **Flask** | Local dev server |
| **FAISS** | Vector store para RAG |
| **OpenAI gpt-4o-mini** | LLM principal |
| **Vercel** | Deploy en producción |

---

## Workflow

1. **Conversación → intent y slot filling** — El bot identifica intent y recoge datos (especie, fecha, etc.)
2. **Selección de día** — El usuario elige día; los tiempos quirúrgicos son internos
3. **Reglas de capacidad** — 240 min/día; límite de perros; duraciones desde tabla maestra
4. **Ventanas de entrega por especie** — Gatos 08:00–09:00; Perros 09:00–10:30
5. **Confirmación** — Instrucciones de entrega + protocolo de ayuno; tiempos quirúrgicos internos

---

## Docs overview

| Documento | Contenido |
|---|---|
| `docs/pre-operative-considerations.md` | Instrucciones preoperatorias, ayuno, transporte, consentimiento |
| `docs/intents-catalog.md` | 20 intents con ejemplos y mapeo a conversaciones |
| `docs/jira/` | Exports Jira enriquecidos |
| `data/rag/instructions-before-operation.en.txt` | Espejo local de la URL oficial para RAG |

---

## Seguridad

- `.env` está en `.gitignore` — nunca se sube al repositorio
- `.env.example` sin secretos disponible como plantilla
- Variables de entorno configuradas en el panel de Vercel (no en el código)

---

## Cursor workflows

- **Implement**: *"Implement PROJ-123"* → agente lee ticket, desarrolla y abre PR
- **Enrich**: *"Enrich VETES-1"* → refina ticket con criterios de aceptación

