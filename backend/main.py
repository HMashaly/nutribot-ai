"""
NutriBot — AI Nutrition Coach
FastAPI Backend: main.py

Run:
    uvicorn main:app --reload --port 8000

Auth: protected endpoints expect the session token as a bearer credential —
`Authorization: Bearer <token>` — surfaced via the `get_current_session`
dependency (and the Authorize button in /docs).
"""

from __future__ import annotations

from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel

from auth import authenticate_user, create_user, get_admin_dashboard_stats
from config import settings
from db import (
    has_fresh_offers,
    init_database,
    get_connection,
    get_memories,
    save_memory,
    load_user_profile,
    save_user_profile,
)
from functions.agent import create_nutribot_agent
from moderation import check_message
from offers.matcher import match_offers
from observability import (
    RequestContextMiddleware,
    configure_langsmith,
    configure_logging,
    current_request_id,
)
from rate_limit import SlidingWindowRateLimiter
from token_counting import run_agent_tracked
from session_manager import SessionManager

API_VERSION = "2.0.0"


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    configure_langsmith()
    logger.info("Starting NutriBot API v{}", API_VERSION)
    init_database()
    logger.info("Database initialised; API ready")

    try:
        if not has_fresh_offers():
            logger.info("Offers cache empty/stale — running offers ingest")
            from offers.ingest import ingest as ingest_offers

            ingest_offers()
    except Exception:
        logger.exception("Offers ingest at startup failed (continuing without it)")

    yield
    logger.info("Shutting down NutriBot API")


# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NutriBot API",
    description="AI Nutrition Coach — LangChain Agent + RAG + Anthropic Claude",
    version=API_VERSION,
    lifespan=lifespan,
)

# Inner middleware first (request correlation), CORS outermost so its headers
# are applied even on early failures.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nutribot-elhoda.netlify.app",
        "https://6a0bffff23b138158275df87--nutribot-elhoda.netlify.app",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "null",           # file:// origin browsers send as "null"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Request-ID"],
)

bearer_scheme = HTTPBearer(auto_error=False, description="Session token from /api/auth/login")

session_manager = SessionManager()
chat_rate_limiter = SlidingWindowRateLimiter(settings.chat_rate_limit_per_minute)

# Bounded LRU of per-(model, user) agents — caps memory in a long-running process.
_agent_cache: "OrderedDict[str, Any]" = OrderedDict()

PROFILE_DEFAULTS: dict = {
    "weight_kg":            70.0,
    "height_cm":            170.0,
    "age":                  30,
    "gender":               "male",
    "activity_level":       "sedentary",
    "goal":                 "maintenance",
    "dietary_restrictions": "",
}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ProfileRequest(BaseModel):
    weight_kg: float | None = None
    height_cm: float | None = None
    age: int | None = None
    gender: str | None = None
    activity_level: str | None = None
    goal: str | None = None
    dietary_restrictions: str | None = None

class ChatRequest(BaseModel):
    message: str
    model: str = "claude-haiku-4-5"
    temperature: float = 0.0
    chat_history: list[dict] = []

class MemoryConfirmRequest(BaseModel):
    memory: str

class OffersRequest(BaseModel):
    ingredients: list[str]


# ── Auth dependencies ──────────────────────────────────────────────────────────

def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Resolve the bearer token to a live session, or 401."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token.")
    session = session_manager.get(credentials.credentials)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return session


def require_admin(session: dict = Depends(get_current_session)) -> dict:
    """Session dependency that additionally enforces the admin role."""
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return session


# ── Internal helpers ───────────────────────────────────────────────────────────

def _format_dietary_profile(profile: dict) -> str:
    restrictions = profile.get("dietary_restrictions") or ""
    return (
        f"Weight: {profile.get('weight_kg', '?')} kg | "
        f"Height: {profile.get('height_cm', '?')} cm | "
        f"Age: {profile.get('age', '?')} | "
        f"Gender: {profile.get('gender', '?')} | "
        f"Activity: {profile.get('activity_level', '?')} | "
        f"Goal: {profile.get('goal', '?')} | "
        f"Dietary restrictions: {restrictions or 'none'}"
    )


def _get_agent(model_name: str, user_id: str):
    cache_key = f"{model_name}:{user_id}"
    agent = _agent_cache.get(cache_key)
    if agent is not None:
        _agent_cache.move_to_end(cache_key)
        return agent

    agent = create_nutribot_agent(model_name=model_name, user_id=user_id)
    _agent_cache[cache_key] = agent
    while len(_agent_cache) > settings.agent_cache_max:
        evicted, _ = _agent_cache.popitem(last=False)
        logger.debug("Evicted agent from cache: {}", evicted)
    return agent


# ── Global error handling ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the full error server-side; return a generic envelope with the
    request ID so a user can quote it without us leaking internals."""
    logger.exception("Unhandled error on {} {}", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": {"error": "Internal server error.", "request_id": current_request_id()}},
    )


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    result = create_user(req.email, req.password)
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message)
    return {"message": result.message}


@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    result = authenticate_user(req.email, req.password, ip_address=ip, user_agent=user_agent)
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message)
    user = result.user
    token = session_manager.create(
        user_id=str(user["id"]),
        email=user["email"],
        role=user.get("role", "user"),
        ip_address=ip,
        user_agent=user_agent,
    )
    logger.info("Login succeeded for user {}", user["id"])
    return {
        "token": token,
        "user_id": str(user["id"]),
        "email": user["email"],
        "role": user.get("role", "user"),
    }


@app.post("/api/auth/me")
async def who_am_i(session: dict = Depends(get_current_session)):
    return {
        "user_id": session["user_id"],
        "email": session["email"],
        "role": session["role"],
        "expires_at": session["expires_at"],
    }


@app.post("/api/auth/logout")
async def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    if credentials and credentials.credentials:
        session_manager.delete(credentials.credentials)
    return {"message": "Signed out."}


# ── Profile ────────────────────────────────────────────────────────────────────

@app.post("/api/profile/get")
async def get_profile(session: dict = Depends(get_current_session)):
    db_profile = load_user_profile(session["user_id"])
    merged = {**PROFILE_DEFAULTS, **{k: v for k, v in db_profile.items() if v is not None}}
    return {"profile": merged}


@app.post("/api/profile/save")
async def save_profile(req: ProfileRequest, session: dict = Depends(get_current_session)):
    updates = req.model_dump(exclude_none=True)
    db_profile = load_user_profile(session["user_id"])
    merged = {**PROFILE_DEFAULTS, **{k: v for k, v in db_profile.items() if v is not None}, **updates}
    save_user_profile(session["user_id"], merged)
    return {"profile": merged}


# ── Chat ───────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest, session: dict = Depends(get_current_session)):
    user_id = session["user_id"]

    allowed, retry_after = chat_rate_limiter.allow(user_id)
    if not allowed:
        logger.warning("Chat rate limit hit for user {}", user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    blocked, reason = check_message(req.message)
    if blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Message blocked ({reason}). Please keep questions nutrition-related.",
        )

    db_profile = load_user_profile(user_id)
    profile = {**PROFILE_DEFAULTS, **{k: v for k, v in db_profile.items() if v is not None}}
    dietary_profile = _format_dietary_profile(profile)

    agent = _get_agent(model_name=req.model, user_id=user_id)

    payload = {
        "input": req.message,
        "dietary_profile": dietary_profile,
        "chat_history": [
            (m["role"], m["content"])
            for m in req.chat_history
            if m.get("role") in ("user", "assistant")
        ],
    }

    # Tag the LangSmith trace with the request's correlation ID, user, and model.
    trace_config = {
        "run_name": "nutribot_chat",
        "tags": ["chat", req.model],
        "metadata": {"user_id": user_id, "request_id": current_request_id()},
    }

    try:
        result, usage = run_agent_tracked(agent, payload, req.model, config=trace_config)
    except Exception:
        logger.exception("Agent run failed for user {}", user_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "The assistant failed to generate a response.",
                "request_id": current_request_id(),
            },
        )

    response_text = result.get("output", "Sorry, I couldn't generate a response.")
    intermediate = result.get("intermediate_steps", [])

    tools_used = []
    sources = []
    pending_memories = []
    offers = []

    for step in intermediate:
        action, observation = step
        tool_name = getattr(action, "tool", "unknown")
        tool_input = getattr(action, "tool_input", {})
        obs_str = str(observation)

        tools_used.append({
            "name": tool_name,
            "input": str(tool_input),
            "output": obs_str[:300],
        })

        if tool_name == "search_nutrition_knowledge":
            for chunk in obs_str.split("\n\n"):
                if chunk.strip():
                    sources.append({"source": "knowledge_base", "content": chunk[:200]})

        if tool_name == "remember_fact":
            fact = str(tool_input.get("fact", "")).strip()
            if fact and fact not in pending_memories:
                pending_memories.append(fact)

        if tool_name == "find_grocery_offers":
            # Re-run the match to attach structured offers for UI cards.
            raw = str(tool_input.get("ingredients", ""))
            items = [p.strip() for p in raw.split(",") if p.strip()]
            if items:
                try:
                    offers.extend(match_offers(items))
                except Exception:
                    logger.exception("Offer enrichment failed for user {}", user_id)

    logger.info(
        "Chat handled for user {} — {} tool call(s), {} tokens",
        user_id, len(tools_used), usage.total_tokens,
    )
    return {
        "response": response_text,
        "tools_used": tools_used,
        "sources": sources,
        "pending_memories": pending_memories,
        "offers": offers,
        "usage": {
            "total_tokens": usage.total_tokens,
            "estimated_cost_usd": round(usage.estimated_cost_usd, 6),
        },
    }


# ── Supermarket offers ─────────────────────────────────────────────────────────

@app.post("/api/offers")
async def grocery_offers(req: OffersRequest, session: dict = Depends(get_current_session)):
    """Find current German supermarket offers for a list of recipe ingredients."""
    matches = match_offers(req.ingredients)
    return {"offers": matches}


# ── Memory (HITL) ──────────────────────────────────────────────────────────────

@app.post("/api/memories/get")
async def get_memories_endpoint(session: dict = Depends(get_current_session)):
    memories = get_memories(session["user_id"])
    return {"memories": memories}


@app.post("/api/memories/confirm")
async def confirm_memory(req: MemoryConfirmRequest, session: dict = Depends(get_current_session)):
    """Human-in-the-loop: user confirms a fact to persist long-term."""
    save_memory(session["user_id"], req.memory)
    return {"message": "Memory saved.", "memory": req.memory}


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.post("/api/admin/stats")
async def admin_stats(session: dict = Depends(require_admin)):
    stats = get_admin_dashboard_stats()
    stats["recent_logins"] = [dict(r) for r in stats["recent_logins"]]
    return stats


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Readiness check — verifies the database is reachable."""
    db_ok = True
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception:
        logger.exception("Health check: database unreachable")
        db_ok = False

    body = {
        "status": "ok" if db_ok else "degraded",
        "version": API_VERSION,
        "database": "up" if db_ok else "down",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if not db_ok:
        return JSONResponse(status_code=503, content=body)
    return body
