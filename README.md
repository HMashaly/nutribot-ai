# NutriBot

NutriBot is a full-stack AI nutrition coach: a FastAPI backend with a LangGraph ReAct agent, a small RAG knowledge base of nutrition reference material, and a set of tools for calculations (BMI, TDEE, macros), dietary compatibility checks, and USDA food lookups. The frontend is a static HTML/JS client.

The agent reasons over a question, decides whether it needs a tool or some retrieved context, runs it, and folds the result back in before answering. It's tied to a per-user profile and a session, and it can remember facts about you long-term — but only after you confirm them.

**Live:**
- App: https://cloudflare-workers-autoconfig-nutribot-ai.h-elmashaly.workers.dev
- API docs: https://elhoda-mashaly-nutribot-backend.hf.space/docs
- Health check: https://elhoda-mashaly-nutribot-backend.hf.space/api/health

## ✨ What it actually does

NutriBot isn't just a chatbot with a system prompt — it's an agent with real tools, a memory, and a couple of features that go beyond "ask an LLM about food":

🧠 **AI nutrition coach** — a LangGraph ReAct agent that reasons over your question, decides which tool(s) it needs, runs them, and folds the results into a grounded answer. Stays on topic: nutrition, diet, food, health, fitness.

📚 **Knowledge-grounded answers** — retrieves from a curated nutrition knowledge base (ChromaDB + multi-query expansion) as a first-class tool, not a pre-processing afterthought. The vector store re-embeds incrementally — only changed source files get reprocessed.

🧮 **Built-in calculators** — BMI, TDEE (activity-adjusted), and full macro splits (protein/carbs/fat in grams *and* calories).

🔍 **USDA food lookups** — real nutrient data for virtually any food via the USDA FoodData Central API.

✅ **Dietary restriction & allergy checking** — tells you whether a food fits **Vegan, Vegetarian, Halal, Kosher**, Gluten-Free, Nut-Free, or Dairy-Free, *and explains why* (flags gelatin/rennet for halal, pork derivatives, shellfish for kosher, alcohol, cross-contamination caveats — not just a yes/no).

👤 **Personal profile & long-term memory** — your saved profile (age, weight, height, activity level, goals, dietary restrictions/allergies) is applied automatically on every turn. The agent can also propose new long-term facts ("I'm lactose intolerant") — but they're only saved once *you* confirm them.

🛒 **Recipe → grocery deals (Angebote)** — give it a meal or recipe and it breaks it into ingredients, then checks which German discounters (Aldi, Lidl, Rewe, Norma, Netto) currently have them on offer — rendered as price/discount cards right under the chat reply.

🎙️ **Voice input** — a 🎤 mic button (browser Web Speech API, EN/DE toggle) dictates your question straight into the chat box. Zero extra dependencies, zero cost.

🔐 **Secure sessions** — register/login with bearer-token sessions, logout/revoke, hashed credentials.

## How it's put together

```
User → Cloudflare-hosted frontend → FastAPI backend → LangGraph agent
                                          │                  │
                                          │                  ├─ RAG retriever (ChromaDB)
                                          │                  ├─ calculation tools (BMI/TDEE/macros)
                                          │                  ├─ dietary compatibility check
                                          │                  ├─ USDA food lookup
                                          │                  └─ long-term memory tool
                                          │
                                    Postgres (Supabase): users, profiles, sessions, memories
```

A message goes through moderation first, then into the agent loop. The agent decides what (if anything) it needs — retrieved docs, a calculation, a food lookup — runs it, and produces a final answer grounded in whatever it pulled in.

| Layer | File |
|---|---|
| Frontend | [`frontend/index.html`](frontend/index.html) |
| Backend API | [`backend/main.py`](backend/main.py) |
| Agent | [`backend/functions/agent.py`](backend/functions/agent.py) |
| RAG (ingest + retriever) | [`backend/rag/`](backend/rag) |
| Tools | [`backend/tools/nutrition_tools.py`](backend/tools/nutrition_tools.py) |
| DB schema | [`backend/sql/schema.sql`](backend/sql/schema.sql) |
| Dependencies | [`backend/pyproject.toml`](backend/pyproject.toml) (managed with `uv`) |

### How the offer data is sourced (the honest version)

German discounters have no free official offers API, and live-scraping all of them on every request won't survive a free Hugging Face Space. So offers are **cached in Postgres** and refreshed by an offline job (`offers/ingest.py`), mirroring the RAG ingest pattern. Each chain is a pluggable **provider**: Aldi is a best-effort live fetch with seed fallback, and the others ship as a **seeded sample dataset** with clearly-marked stub adapters, so the feature always demos while real per-chain scrapers can be added later without touching the agent or UI. (Rewe, for the record, now requires an app certificate, so it stays seed-backed.)

## Security & operations

The backend is built to run unattended, not just demo locally:

- **Bearer-token auth** — protected endpoints take the session token via `Authorization: Bearer <token>`, wired through a FastAPI dependency, so `/docs` gets a working **Authorize** button. Tokens are stored **hashed** (SHA-256) server-side; passwords use bcrypt.
- **Abuse protection** — login is rate-limited with an audit trail, and the expensive `/api/chat` endpoint has its own per-user sliding-window limit.
- **Request correlation** — every request gets an `X-Request-ID` that threads through structured logs (and is echoed back on errors), so a user can quote one ID and you can trace the whole request.
- **Optional LangSmith tracing** — flip `LANGCHAIN_TRACING_V2=true` and agent runs are traced end-to-end, tagged with the user and request ID.
- **Deep health check** — `/api/health` actually pings the database and returns `503` when it can't reach it, instead of lying with a static `ok`.
- **No info leaks** — unhandled errors are logged in full server-side and returned to the client as a generic envelope plus the request ID.

## Stack

Python 3.11, FastAPI, LangChain + LangGraph, ChromaDB, OpenAI (generation + embeddings), PostgreSQL, optional Mistral moderation, Docker, `uv` for dependencies.

## Running it locally

### Backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

API docs at http://127.0.0.1:8000/docs

### Frontend

Just open `frontend/index.html`, or serve it:

```bash
cd frontend
python3 -m http.server 3000
```

## Environment variables

Copy `backend/.env.example` to `backend/.env`.

Required:

```env
OPENAI_API_KEY=sk-proj-...
DATABASE_URL=postgresql://user:password@host:5432/nutrition_db
```

Optional:

```env
MISTRAL_API_KEY=
USDA_API_KEY=DEMO_KEY
SESSION_MAX_HOURS=8

# Abuse protection
CHAT_RATE_LIMIT_PER_MINUTE=20
AGENT_CACHE_MAX=256

# Observability
LOG_LEVEL=INFO
LOG_FORMAT=console            # console | json

# LangSmith tracing (leave disabled if you have no key)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=nutribot
```

## Building the vector store

```bash
cd backend
uv run python rag/ingest.py
```

Writes to `backend/chroma_db/`. Only changed source files get re-embedded.

## Refreshing supermarket offers

Offers are cached in Postgres and rotate weekly. Refresh the cache with:

```bash
cd backend
uv run python offers/ingest.py
```

Or set `RUN_OFFERS_INGEST=1` to refresh on container startup (like `RUN_RAG_INGEST`).

## Tests

```bash
cd backend
uv run pytest tests/ -v
```

## Docker

```bash
cd backend
docker build -t nutribot-backend .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-... \
  -e DATABASE_URL=postgresql://user:password@host:5432/nutrition_db \
  nutribot-backend
```

Set `RUN_RAG_INGEST=1` to rebuild the vector store on container startup.

## Deployment notes

- **Frontend** → Cloudflare Workers/Pages, served straight from `frontend/`
- **Backend** → a Hugging Face Docker Space, repo root as the build context
- **Database** → Supabase Postgres, schema from `backend/sql/schema.sql`

For the backend Space, set secrets `DATABASE_URL`, `OPENAI_API_KEY`, and `MISTRAL_API_KEY` (if you're using moderation), plus optional variables `USDA_API_KEY`, `SESSION_MAX_HOURS`, `RUN_RAG_INGEST`.

For the frontend, point the API base URL in `frontend/index.html` at the backend's domain before deploying.

A couple of gotchas: CORS origins are hardcoded in the backend, and free Hugging Face Spaces cold-start after sitting idle for a while.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create an account |
| POST | `/api/auth/login` | Log in, get a session token |
| POST | `/api/auth/me` | Validate the current session |
| POST | `/api/auth/logout` | Revoke the current session |
| POST | `/api/profile/get` | Load the saved profile |
| POST | `/api/profile/save` | Save/update the profile |
| POST | `/api/chat` | Send a message to the agent |
| POST | `/api/offers` | Find supermarket offers for a list of ingredients |
| POST | `/api/memories/get` | Fetch confirmed long-term memories |
| POST | `/api/memories/confirm` | Save a confirmed memory |
| POST | `/api/admin/stats` | Admin usage stats |
| GET | `/api/health` | Health check |

## Repo layout

```
nutribot1/
├── frontend/
│   └── index.html
└── backend/
    ├── main.py              FastAPI entry point
    ├── Dockerfile
    ├── pyproject.toml       uv dependency manifest
    ├── functions/agent.py   LangGraph agent
    ├── rag/                 ChromaDB + retriever
    ├── offers/              supermarket offer providers, matcher, ingest
    ├── tools/               calculation, USDA, memory, grocery-offer tools
    ├── observability.py     logging, request IDs, tracing
    ├── knowledgebase/       nutrition source documents
    ├── sql/schema.sql       Postgres schema
    └── tests/
```

## Contributing

Bugs and ideas → open an issue. PRs welcome — keep them focused and add tests for behavior changes.
