# 🥗 NutriBot — AI Nutrition Coach

> **An AI-powered nutrition coaching platform** built with LangChain, RAG (ChromaDB), OpenAI GPT-4o, FastAPI, and PostgreSQL — featuring a decoupled JS frontend deployed to Netlify.

---

## 📌 Project Purpose

**NutriBot** addresses a critical gap in personal health management: generic chatbots cannot provide *personalised*, *dietary-restriction-aware*, *calculation-grounded* nutrition guidance. Most people rely on one-size-fits-all advice that ignores their weight, goals, halal/vegan constraints, or actual caloric needs.

**The problem it solves:** Users need a trustworthy, domain-restricted AI coach that retrieves expert-curated nutritional knowledge (RAG), runs precise calculations (BMI, TDEE, macros), validates food against dietary restrictions, and remembers their preferences across sessions — all within an ethical, moderated, and authenticated environment.

**How it works:** A user authenticates, sets their health profile (weight, height, activity level, goal, dietary restrictions), and converses with a LangChain tool-calling agent. The agent dynamically routes each query to the right tool — RAG semantic search, calculation tools, USDA food lookup, or direct GPT response — then returns a grounded, personalised answer. Long-term memory is gated behind a Human-in-the-Loop (HITL) confirmation step before any fact is persisted.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Netlify (free, permanent)                         │
│      frontend/index.html — Vanilla JS SPA                   │
│  Auth · Profile · Chat UI · HITL · Stats · JSON Export      │
└──────────────────────────┬──────────────────────────────────┘
                           │  REST API (HTTPS)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           FastAPI Backend (Railway / Render / Fly.io)       │
│  main.py — /api/auth · /api/profile · /api/chat · /api/mem │
│  session_manager.py — token-based sessions (8h TTL)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           LangChain AgentExecutor (functions/agent.py)      │
│  System rules + live user profile injected on every invoke  │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
RAG Tool   BMI/TDEE  Macros   DietCheck  USDA API   remember_fact
ChromaDB   Calculator          Validator  FoodData   → HITL gate
   │
   ▼
OpenAI text-embedding-3-small
Mistral moderation API

PostgreSQL: users · login_audit · user_memories · user_profiles
```

---

## ✨ Features

### AI Agent (Case 2 — AI Agent for Task Automation + Case 1 — RAG)
| Capability | Implementation |
|---|---|
| 🤖 LangChain Agent | `create_tool_calling_agent` + `AgentExecutor` (modern, not deprecated ReAct) |
| 📚 RAG | ChromaDB + OpenAI `text-embedding-3-small` + `MultiQueryRetriever` (3 variants / query) |
| 🔢 BMI Calculator | Mifflin–St Jeor formula, WHO categories |
| 🔥 TDEE / Calories | Full BMR → TDEE → goal-adjusted target pipeline |
| 🥗 Macros | Goal-specific protein/carb/fat ratios in grams |
| 🌿 Dietary Check | Keyword-rule engine for vegan / vegetarian / halal / kosher / gluten-free / nut-free / dairy-free |
| 🍎 USDA Lookup | Live `FoodData Central` API — per-100g nutritional data |
| 🧠 Long-term Memory | PostgreSQL `user_memories` — HITL-confirmed only |

### Backend (FastAPI)
- REST endpoints replacing Streamlit's server-side logic
- Opaque token sessions with 8-hour TTL
- Mistral moderation on every message (jailbreak + violence guard)
- bcrypt password hashing, rate limiting (5 attempts / 5 min), login audit log

### Frontend (Vanilla JS → Netlify)
- Zero build-step SPA — pure HTML/CSS/JS, one file
- Deploys to **Netlify** free tier: **permanent**, no sleep, global CDN, custom domain support
- Responsive sidebar (mobile-friendly hamburger menu)
- Profile auto-save on every field change
- HITL memory confirmation cards inline in chat
- Session usage stats (tokens + estimated USD cost)
- One-click JSON export of full session

---

## 🚀 Deployment Guide

### Frontend → Netlify (permanent free hosting)

1. Go to [netlify.com](https://netlify.com) and sign up (free, no credit card).
2. Drag the `frontend/` folder into the Netlify dashboard → instant deploy.
3. **Or** connect your GitHub repo: Netlify auto-deploys on every push.
4. Edit `frontend/index.html` line 4 — replace `YOUR_BACKEND_URL_HERE` with your backend URL.
5. Your app is live at `https://yourapp.netlify.app` — **forever free, no sleep**.

### Backend → Railway (recommended, free tier available)

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login & init
railway login
railway init

# 3. Set environment variables in Railway dashboard:
#    OPENAI_API_KEY, DATABASE_URL, MISTRAL_API_KEY (optional), USDA_API_KEY (optional)

# 4. Deploy
railway up
```

**Alternative free backends:** [Render](https://render.com) (free tier, spins down after 15min idle) · [Fly.io](https://fly.io) (3 free VMs)

### Backend — Local Setup

```bash
# 1. Clone & enter backend
cd nutribot/backend

# 2. Virtual environment
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and DATABASE_URL

# 5. Init PostgreSQL (free cloud: https://neon.tech)
psql $DATABASE_URL < sql/schema.sql

# 6. Build RAG knowledge base (ONE TIME)
python rag/ingest.py

# 7. Run
uvicorn main:app --reload --port 8000
```

### Environment Variables

```env
# Required
OPENAI_API_KEY=sk-proj-...
DATABASE_URL=postgresql://user:pass@host:5432/nutrition_db

# Optional
MISTRAL_API_KEY=...       # Enables content moderation
USDA_API_KEY=DEMO_KEY     # 1000 req/day free — register at api.nal.usda.gov
MODEL_NAME=gpt-4o-mini
TEMPERATURE=0.0
```

---

## 📂 Repository Structure

```
nutribot/
├── backend/                        # FastAPI Python backend
│   ├── main.py                     # REST API — all endpoints
│   ├── session_manager.py          # Token-based session store
│   ├── auth.py                     # bcrypt auth + rate limiting
│   ├── db.py                       # PostgreSQL helpers
│   ├── config.py                   # pydantic-settings config
│   ├── moderation.py               # Mistral moderation wrapper
│   ├── token_counting.py           # Token + cost tracking
│   ├── functions/
│   │   └── agent.py                # LangChain AgentExecutor wiring
│   ├── rag/
│   │   ├── ingest.py               # Incremental embedding pipeline
│   │   └── retriever.py            # MultiQueryRetriever as LangChain tool
│   ├── tools/
│   │   └── nutrition_tools.py      # BMI, TDEE, Macros, DietCheck, USDA
│   ├── knowledgebase/              # 6 markdown nutrition knowledge files
│   ├── sql/
│   │   └── schema.sql              # PostgreSQL DDL (idempotent)
│   ├── tests/
│   │   └── test_tools.py           # Unit tests for nutrition tools
│   └── requirements.txt
│
└── frontend/                       # Netlify-deployed SPA
    ├── index.html                  # Complete app — HTML + CSS + JS
    └── netlify.toml                # Netlify routing config
```

---

## 🧪 Evaluation Criteria Mapping

### Outcome Quality (Case 1 + Case 2)
| Requirement | Evidence |
|---|---|
| Completeness | Full auth → profile → agent → RAG → memory pipeline working end-to-end |
| User interface | Polished dark-mode SPA with sidebar profile, chat, HITL cards, usage stats |
| Project goal clarity | This README section |

### Learning Application
| Requirement | Evidence |
|---|---|
| LangChain | `create_tool_calling_agent` + `AgentExecutor` + `MultiQueryRetriever` |
| ChromaDB / Vector DB | Persisted vectorstore with incremental ingest |
| LLM APIs | OpenAI `ChatOpenAI` + `text-embedding-3-small`; Mistral moderation |
| Prompt engineering | Dual system messages; profile injected on every invoke |
| Best practices | Tool docstrings as descriptions; factory pattern; no Streamlit imports in agent |

### Ethical Considerations
| Risk | Mitigation |
|---|---|
| **Medical misinformation** | Domain restriction in system prompt; always recommends consulting a professional |
| **Dietary harm** | Conservative dietary checker; warns about cross-contamination; fail-safe keyword rules |
| **Data privacy** | bcrypt passwords; HITL before persisting any personal fact; login audit trail |
| **Content abuse** | Mistral moderation on every message; blocks jailbreak + violence categories |
| **Bias** | Knowledge base is curated from WHO/NHS-aligned sources; no single cultural bias |
| **Over-reliance** | Disclaimer in every response: "This is not medical advice" |

### Presentation (SCR Framework)
- **Situation:** Users lack personalised, trustworthy nutrition guidance and rely on generic chatbots
- **Complication:** Generic AI ignores dietary restrictions, can't do precise calculations, and has no persistent memory
- **Resolution:** NutriBot — a domain-restricted LangChain agent with RAG, 6 specialised tools, HITL memory, and secure auth; accessible via a production-ready decoupled architecture

---

## 🛠️ API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Returns session token |
| POST | `/api/auth/logout` | token | Invalidate session |
| POST | `/api/profile/get` | token | Load saved profile |
| POST | `/api/profile/save` | token | Upsert profile to DB |
| POST | `/api/chat` | token | Send message → agent response |
| POST | `/api/memories/get` | token | List confirmed memories |
| POST | `/api/memories/confirm` | token | HITL — persist a memory |
| POST | `/api/admin/stats` | admin token | User + audit stats |
| GET  | `/api/health` | — | Health check |

---

## ⚠️ Known Limitations & Future Work

| Issue | Suggested Fix |
|---|---|
| In-memory sessions reset on restart | Swap `SessionManager` dict for Redis |
| ChromaDB is single-tenant | Migrate to Pinecone or Weaviate for multi-user vectorstore |
| Cost table hardcoded | Pull from OpenAI pricing API |
| No per-message feedback | Add 👍👎 buttons + `user_feedback` DB table |
| Frontend calls backend directly | Add a BFF (Backend for Frontend) or API gateway for rate limiting per user |

---

## 📄 License

MIT — commercial use allowed.

---

*Built for the Turing College AI Engineering Capstone · May 2026 | Python 3.11 · FastAPI 0.115 · LangChain 0.3 · Netlify*
