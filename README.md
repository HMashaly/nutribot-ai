# NutriBot

NutriBot is an AI nutrition coaching application built with a FastAPI backend, a static frontend, retrieval over a curated nutrition knowledge base, and PostgreSQL-backed authentication, profiles, memory, and session state.

The project brings together `LangGraph` for agent orchestration, `LangChain` for tools and retrieval, `ChromaDB` for vector search, and OpenAI models for generation and embeddings. The chat system follows a ReAct-style agent loop, where the model reasons about the next step, uses tools when needed, observes tool results, and continues toward a grounded final answer.

## Architecture

The system is organized as a small full-stack application with a clear split between UI, API, orchestration, retrieval, and persistence.

```mermaid
flowchart LR
    user["User"]
    frontend["Frontend<br/>Static HTML / CSS / JavaScript"]
    backend["FastAPI Backend<br/>main.py"]
    agent["LangGraph Agent<br/>functions/agent.py"]
    tools["Nutrition Tools<br/>calculations, USDA, memory"]
    rag["RAG Layer<br/>ChromaDB + retriever"]
    db["PostgreSQL<br/>users, profiles, sessions, audits"]
    openai["OpenAI Models<br/>generation + embeddings"]
    mistral["Mistral Moderation<br/>(optional)"]

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

- **Frontend:** static HTML/CSS/JavaScript app in [frontend/index.html](/Users/h/Turing/Capestone/nutribot1/frontend/index.html)
- **Backend:** FastAPI API in [backend/main.py](/Users/h/Turing/Capestone/nutribot1/backend/main.py)
- **Agent orchestration:** LangGraph-backed agent in [backend/functions/agent.py](/Users/h/Turing/Capestone/nutribot1/backend/functions/agent.py)
- **Retrieval layer:** ChromaDB + LangChain retriever in [backend/rag](/Users/h/Turing/Capestone/nutribot1/backend/rag)
- **Persistence:** PostgreSQL schema in [backend/sql/schema.sql](/Users/h/Turing/Capestone/nutribot1/backend/sql/schema.sql)
- **Dependency management:** `uv` with [backend/pyproject.toml](/Users/h/Turing/Capestone/nutribot1/backend/pyproject.toml) and [backend/uv.lock](/Users/h/Turing/Capestone/nutribot1/backend/uv.lock)

## What This Project Demonstrates

This project was not built as a single-prompt chatbot. It applies several of the concepts typically covered across modern LLM application material and turns them into one working system.

| Capability | Implementation |
| --- | --- |
| `LangChain architecture` | LangChain is used for models, messages, tools, retrieval, and memory-oriented application flow. |
| `LangGraph orchestration` | The agent is orchestrated with LangGraph in [backend/functions/agent.py](/Users/h/Turing/Capestone/nutribot1/backend/functions/agent.py) rather than a fixed request-response chain. |
| `ReAct-style agent loop` | The chat flow follows a reason -> act -> observe pattern, with tool results fed back into the agent before the final answer. |
| `RAG` | Answers are grounded with a curated nutrition knowledge base, embeddings, and ChromaDB retrieval instead of relying only on model recall. |
| `Agentic RAG` | Retrieval is part of the tool-using agent loop, not a one-step pipeline bolted in front of generation. |
| `Multi-query retrieval` | The retriever expands questions into multiple query variants to improve recall for differently phrased nutrition intents. |
| `Function calling / tools` | The assistant can call nutrition calculation tools, a dietary compatibility tool, a USDA lookup tool, and a memory tool. |
| `Memory` | The app combines session context, saved user profile data, and long-term confirmed memories. |
| `Human-in-the-loop` | Durable user facts are only written to long-term memory after explicit user confirmation. |
| `Grounded personalization` | Responses are personalized from persisted profile data and durable user facts while still staying grounded in retrieved knowledge. |
| `Production concerns` | The backend includes authentication, PostgreSQL-backed sessions, rate limiting, moderation, typed config, tests, Docker support, and reproducible installs with `uv`. |
| `Incremental ingest` | Knowledge ingestion uses hash-based re-embedding so changed source files can be refreshed deliberately instead of full reprocessing every time. |
| `Operational reliability` | Logging and backend test coverage are included to support debugging and safer iteration. |

**Agentic orchestration with LangGraph**

The request cycle below reflects the current chat flow in the backend, including moderation before agent execution and the tool-observation loop inside the LangGraph agent.

```mermaid
flowchart TD
    user["User Question"] --> frontend["Frontend Request"]
    frontend --> chat["FastAPI /api/chat"]
    chat --> moderation["Moderation Check"]
    moderation --> agent["LangGraph ReAct Agent"]
    agent --> decide{"Need a tool?"}
    decide -->|Yes| tools["Tools / RAG Retrieval"]
    tools --> observation["Tool Result / Observation"]
    observation --> agent
    decide -->|No| answer["Final Answer"]
    answer --> response["API Response"]
    response --> frontend
```

## Implemented Capabilities

- Nutrition-focused chat API with domain-restricted assistant behavior
- Profile-aware responses using persisted user profile data
- Retrieval-augmented generation over curated nutrition documents
- Tool-backed calculations for BMI, calorie targets, and macronutrients
- Dietary compatibility checks for common restriction types
- USDA food lookup tool
- Human-confirmed long-term memory storage
- Human-in-the-loop confirmation before durable memory is saved
- PostgreSQL-backed authentication, login audit history, and server-side session management
- Session restoration via backend validation on frontend startup
- Login rate limiting based on recent failed login attempts
- Input moderation gate before agent execution
- Incremental embedding ingest with file hash tracking
- Unit tests for auth/session behavior and core tool logic

## Tech Stack

- Python 3.11
- FastAPI
- LangChain
- LangGraph
- ChromaDB
- PostgreSQL
- OpenAI API
- `uv`
- Docker

## Local Development

### 1. Backend

```bash
cd /Users/h/Turing/Capestone/nutribot1/backend
uv sync
uv run uvicorn main:app --reload
```

Backend API docs:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Frontend

Open the frontend directly:

- [frontend/index.html](/Users/h/Turing/Capestone/nutribot1/frontend/index.html)

Or serve it locally:

```bash
cd /Users/h/Turing/Capestone/nutribot1/frontend
python3 -m http.server 3000
```

Local frontend URL:

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

## Environment Variables

Create a `.env` in `backend/` based on [backend/.env.example](/Users/h/Turing/Capestone/nutribot1/backend/.env.example).

Required:

```bash
OPENAI_API_KEY=sk-proj-...
DATABASE_URL=postgresql://user:password@host:5432/nutrition_db
```

Optional:

```bash
MISTRAL_API_KEY=
USDA_API_KEY=DEMO_KEY
SESSION_MAX_HOURS=8
```

## Retrieval Ingest

To build or refresh the vector store locally:

```bash
cd /Users/h/Turing/Capestone/nutribot1/backend
uv run python rag/ingest.py
```

This writes local vector data to `backend/chroma_db`.

## Testing

Run the backend test suite:

```bash
cd /Users/h/Turing/Capestone/nutribot1/backend
uv run pytest tests/ -v
```

## Docker

The backend container is defined in [backend/Dockerfile](/Users/h/Turing/Capestone/nutribot1/backend/Dockerfile).

Build and run:

```bash
cd /Users/h/Turing/Capestone/nutribot1/backend
docker build -t nutribot-backend .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-... \
  -e DATABASE_URL=postgresql://user:password@host:5432/nutrition_db \
  nutribot-backend
```

Optional startup ingest:

```bash
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-... \
  -e DATABASE_URL=postgresql://user:password@host:5432/nutrition_db \
  -e RUN_RAG_INGEST=1 \
  nutribot-backend
```

## Deployment

Current configured deployment targets in the application:

- **Frontend:** Netlify  
  [https://nutribot-elhoda.netlify.app](https://nutribot-elhoda.netlify.app)
- **Backend:** Render  
  [https://nutribot-1-5xzm.onrender.com](https://nutribot-1-5xzm.onrender.com)

Notes:

- The frontend uses the Render backend URL outside local development.
- CORS is currently hardcoded in the backend to preserve the deployed frontend behavior.
- Sessions are validated via `POST /api/auth/me` when the frontend restores login state.

## Repository Structure

- [backend](/Users/h/Turing/Capestone/nutribot1/backend): API, auth, sessions, RAG, tools, tests, Docker files
- [frontend](/Users/h/Turing/Capestone/nutribot1/frontend): static client and Netlify config
- [backend/knowledgebase](/Users/h/Turing/Capestone/nutribot1/backend/knowledgebase): nutrition source documents
- [backend/tests](/Users/h/Turing/Capestone/nutribot1/backend/tests): backend unit tests

## Contributing

External contributions are welcome.

- Open an issue for bugs, ideas, or discussion
- Submit a pull request with a focused change
- Keep changes scoped and include tests where behavior changes
