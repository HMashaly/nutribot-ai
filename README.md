<div align="center">

# 🥦 NutriBot

### *Your AI-Powered Nutrition Coach*

> A domain-restricted, retrieval-augmented, tool-using AI assistant that delivers personalized nutritional guidance — grounded in expert knowledge, backed by precise calculations, and secured with full authentication.

<br/>

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

<br/>

🌐 **[Live App](https://cloudflare-workers-autoconfig-nutribot-ai.h-elmashaly.workers.dev)** &nbsp;|&nbsp;
⚡ **[API Docs](https://elhoda-mashaly-nutribot-backend.hf.space/docs)** &nbsp;|&nbsp;
💚 **[Health Check](https://elhoda-mashaly-nutribot-backend.hf.space/api/health)**

</div>

---

## 🌿 What Is NutriBot?

NutriBot is a full-stack AI application that acts as a personal nutrition coach. It combines a **LangGraph-orchestrated ReAct agent**, a **curated RAG knowledge base**, and a suite of **domain-specific tools** to answer nutrition questions with accuracy, personalization, and transparency.

A user authenticates, builds a health profile, and chats with an agent that reasons over retrieved knowledge, runs calculations, and remembers confirmed preferences — all within an ethical, rate-limited, and moderated environment.

---

## 🚀 Live Deployment

| 🏗️ Service | ⚙️ Role | 🔗 URL |
|:---:|:---:|:---|
| **Cloudflare Workers** | Frontend | [cloudflare-workers-autoconfig-nutribot-ai.h-elmashaly.workers.dev](https://cloudflare-workers-autoconfig-nutribot-ai.h-elmashaly.workers.dev) |
| **Hugging Face Spaces** | Backend API | [elhoda-mashaly-nutribot-backend.hf.space](https://elhoda-mashaly-nutribot-backend.hf.space) |
| **Supabase** | PostgreSQL Database | Managed Postgres via `DATABASE_URL` |

---

## 🧠 How It Works

```
User → Authenticates → Sets Health Profile → Chats with Agent
                                                      ↓
                               ┌──────────────────────────────────┐
                               │        LangGraph ReAct Loop      │
                               │  Reason → Use Tool → Observe     │
                               │  → Reason → Final Answer         │
                               └──────────────────────────────────┘
                                              ↓
                     Grounded · Personalized · Calculation-Backed
```

Each message is **moderated**, then passed to the agent, which dynamically chooses between:

- 📚 Retrieving from the nutrition knowledge base
- 🔢 Running BMI / TDEE / macro calculations
- 🥗 Checking dietary compatibility
- 🔍 Looking up foods via the USDA database
- 🧠 Recalling confirmed long-term memories

> Long-term memory is only persisted after **explicit user confirmation** — nothing is stored without your approval.

---

## 🗺️ System Architecture

```mermaid
flowchart LR
    user["👤 User"]
    frontend["🖥️ Frontend\nStatic HTML / CSS / JS"]
    backend["⚡ FastAPI Backend\nmain.py"]
    agent["🤖 LangGraph Agent\nfunctions/agent.py"]
    tools["🔧 Nutrition Tools\ncalculations, USDA, memory"]
    rag["📚 RAG Layer\nChromaDB + retriever"]
    db["🗄️ PostgreSQL\nusers, profiles, sessions"]
    openai["🧠 OpenAI Models\ngeneration + embeddings"]
    mistral["🛡️ Mistral Moderation\n(optional)"]

    user --> frontend
    frontend --> backend
    backend --> mistral
    backend --> agent
    agent --> tools
    agent --> rag
    tools --> db
    backend --> db
    rag --> openai
    agent --> openai
```

| Layer | File |
|:---|:---|
| 🖥️ Frontend | [`frontend/index.html`](frontend/index.html) |
| ⚡ Backend API | [`backend/main.py`](backend/main.py) |
| 🤖 Agent Orchestration | [`backend/functions/agent.py`](backend/functions/agent.py) |
| 📚 Retrieval (RAG) | [`backend/rag/`](backend/rag) |
| 🗄️ Database Schema | [`backend/sql/schema.sql`](backend/sql/schema.sql) |
| 📦 Dependencies | [`backend/pyproject.toml`](backend/pyproject.toml) via `uv` |

---

## ⚙️ Agent Flow

```mermaid
flowchart TD
    user["💬 User Question"] --> frontend["🖥️ Frontend Request"]
    frontend --> chat["⚡ FastAPI /api/chat"]
    chat --> moderation["🛡️ Moderation Check"]
    moderation --> agent["🤖 LangGraph ReAct Agent"]
    agent --> decide{"🤔 Need a tool?"}
    decide -->|Yes| tools["🔧 Tools / RAG Retrieval"]
    tools --> observation["👁️ Tool Result / Observation"]
    observation --> agent
    decide -->|No| answer["✅ Final Answer"]
    answer --> response["📤 API Response"]
    response --> frontend
```

---

## ✨ Capabilities

| 🏷️ Capability | 💡 How It's Built |
|:---|:---|
| 🤖 **LangGraph Orchestration** | Agent graph instead of a fixed request-response chain |
| 🔄 **ReAct Agent Loop** | Reason → Act → Observe cycle with tool results fed back before the final answer |
| 📚 **Retrieval-Augmented Generation** | Curated nutrition documents embedded into ChromaDB; answers grounded in sources |
| 🔗 **Agentic RAG** | Retrieval is a first-class tool in the agent loop, not a pre-processing step |
| 🔍 **Multi-Query Retrieval** | Questions expanded into multiple variants for better recall across phrasing |
| 🔧 **Function Calling / Tools** | BMI, TDEE, macros, dietary compatibility, USDA food lookup, memory tool |
| 🧠 **Layered Memory** | Session context + persisted profile + confirmed long-term facts |
| 🙋 **Human-in-the-Loop** | Durable facts require explicit user confirmation before being saved |
| 🎯 **Grounded Personalization** | Profile-aware responses anchored in retrieved knowledge |
| 🏭 **Production-Ready** | Auth, rate limiting, moderation, typed config, tests, Docker, `uv` |
| ♻️ **Incremental Ingest** | Hash-based re-embedding — only changed files are reprocessed |

---

## 🛠️ Tech Stack

<div align="center">

| 🧩 Technology | 🎯 Role |
|:---:|:---|
| ![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat-square&logo=python&logoColor=white) | Core language |
| ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) | REST API framework |
| ![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white) | Tools, retrieval, memory |
| ![LangGraph](https://img.shields.io/badge/LangGraph-FF6B35?style=flat-square&logoColor=white) | Agent orchestration |
| ![ChromaDB](https://img.shields.io/badge/ChromaDB-FF4081?style=flat-square&logoColor=white) | Vector store |
| ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white) | Generation + embeddings |
| ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat-square&logo=postgresql&logoColor=white) | Persistence layer |
| ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) | Containerization |
| ![uv](https://img.shields.io/badge/uv-DE5FE9?style=flat-square&logoColor=white) | Dependency management |

</div>

---

## 💻 Local Development

### 🔧 Backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

📖 Interactive API docs → [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 🖥️ Frontend

Open [`frontend/index.html`](frontend/index.html) directly, or serve locally:

```bash
cd frontend
python3 -m http.server 3000
```

🌐 Local URL → [http://127.0.0.1:3000](http://127.0.0.1:3000)

---

## 🔐 Environment Variables

Create `backend/.env` from [`backend/.env.example`](backend/.env.example).

**Required**

```env
OPENAI_API_KEY=sk-proj-...
DATABASE_URL=postgresql://user:password@host:5432/nutrition_db
```

**Optional**

```env
MISTRAL_API_KEY=
USDA_API_KEY=DEMO_KEY
SESSION_MAX_HOURS=8
```

---

## 📦 Retrieval Ingest

Build or refresh the local vector store:

```bash
cd backend
uv run python rag/ingest.py
```

> Vector data is written to `backend/chroma_db/`. Only changed files are re-embedded.

---

## 🧪 Testing

```bash
cd backend
uv run pytest tests/ -v
```

---

## 🐳 Docker

```bash
cd backend
docker build -t nutribot-backend .

docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-... \
  -e DATABASE_URL=postgresql://user:password@host:5432/nutrition_db \
  nutribot-backend
```

To trigger RAG ingest on startup, add `-e RUN_RAG_INGEST=1`.

---

## ☁️ Deployment

### Infrastructure Overview

| 🏗️ Platform | ⚙️ What Runs There | 📝 Notes |
|:---|:---|:---|
| **Cloudflare Workers** | Static frontend from `frontend/` | Public browser entry point |
| **Hugging Face Spaces** | Dockerized FastAPI backend | REST API + Swagger at `/docs` |
| **Supabase** | Managed PostgreSQL | Users, profiles, sessions, memories, audit logs |

### 🔧 Backend Deployment

1. Create a Supabase project and run [`backend/sql/schema.sql`](backend/sql/schema.sql) in the SQL Editor
2. Copy the Supabase **session pooler** connection string into `DATABASE_URL`
3. Create a Hugging Face **Docker Space** with the backend files at the repo root
4. Add Space **secrets** — `DATABASE_URL`, `OPENAI_API_KEY`, `MISTRAL_API_KEY` (if used)
5. Add Space **variables** — `USDA_API_KEY=DEMO_KEY`, `SESSION_MAX_HOURS=8`, `RUN_RAG_INGEST=1` (optional)
6. Push to the Space repo — Hugging Face rebuilds and redeploys automatically
7. Verify at `/api/health` and `/docs`

### 🖥️ Frontend Deployment

1. Update the production API base URL in [`frontend/index.html`](frontend/index.html) to the Hugging Face backend domain
2. Deploy `frontend/` to Cloudflare Workers / Pages
3. Smoke-test login, profile save, chat, and memory confirmation against the live backend

> ⚠️ **Note:** CORS origins are hardcoded in the backend. Hugging Face free Spaces may cold-start after a period of inactivity.

---

## 📡 API Reference

| 🔵 Method | 🔗 Endpoint | 📋 Purpose |
|:---:|:---|:---|
| `POST` | `/api/auth/register` | Create a user account |
| `POST` | `/api/auth/login` | Sign in and receive a session token |
| `POST` | `/api/auth/me` | Validate the current session token |
| `POST` | `/api/auth/logout` | Revoke the current session |
| `POST` | `/api/profile/get` | Load the saved user profile |
| `POST` | `/api/profile/save` | Save or update the user profile |
| `POST` | `/api/chat` | Send a nutrition question to the agent |
| `POST` | `/api/memories/get` | Fetch confirmed long-term memories |
| `POST` | `/api/memories/confirm` | Persist a user-confirmed memory |
| `POST` | `/api/admin/stats` | Admin-only usage and login statistics |
| `GET` | `/api/health` | Health check |

---

## 📁 Repository Structure

```
nutribot1/
├── 🖥️  frontend/                  Static client (local + Cloudflare)
│   └── index.html
│
└── ⚡  backend/
    ├── main.py                   FastAPI entry point
    ├── Dockerfile
    ├── pyproject.toml            uv dependency manifest
    ├── functions/
    │   └── agent.py              LangGraph ReAct agent
    ├── rag/                      ChromaDB + LangChain retriever
    ├── knowledgebase/            Nutrition source documents
    ├── sql/
    │   └── schema.sql            PostgreSQL schema
    └── tests/                    Backend unit tests
```

---

## 🤝 Contributing

Contributions are welcome and appreciated!

- 🐛 **Bugs & ideas** — open an issue
- 🔀 **Pull requests** — keep changes focused and include tests where behavior changes

---

<div align="center">

Made with 🥦 and a lot of ☕

</div>
