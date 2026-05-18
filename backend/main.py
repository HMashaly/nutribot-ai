"""
NutriBot — AI Nutrition Coach
FastAPI Backend: main.py

Replaces Streamlit app.py with a proper REST API.

Run:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import authenticate_user, create_user, get_admin_dashboard_stats
from db import (
    init_database,
    get_memories,
    save_memory,
    load_user_profile,
    save_user_profile,
)
from moderation import check_message
from token_counting import count_tokens, estimate_cost, run_agent_tracked
from session_manager import SessionManager

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NutriBot API",
    description="AI Nutrition Coach — LangChain Agent + RAG + OpenAI",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to your Netlify URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_manager = SessionManager()
_agent_cache: dict[str, Any] = {}

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
    token: str
    weight_kg: float | None = None
    height_cm: float | None = None
    age: int | None = None
    gender: str | None = None
    activity_level: str | None = None
    goal: str | None = None
    dietary_restrictions: str | None = None

class ChatRequest(BaseModel):
    token: str
    message: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    chat_history: list[dict] = []

class MemoryConfirmRequest(BaseModel):
    token: str
    memory: str

class TokenOnlyRequest(BaseModel):
    token: str

# ── Internal helpers ───────────────────────────────────────────────────────────

def _require_session(token: str) -> dict:
    session = session_manager.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return session


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
    if cache_key not in _agent_cache:
        agent_module = importlib.import_module("functions.agent")
        _agent_cache[cache_key] = agent_module.create_nutribot_agent(
            model_name=model_name,
            user_id=user_id,
        )
    return _agent_cache[cache_key]


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_database()


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(req: RegisterRequest, request: Request):
    result = create_user(req.email, req.password)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    return {"message": result.message}


@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    ip = request.client.host if request.client else None
    result = authenticate_user(req.email, req.password, ip_address=ip)
    if not result.ok:
        raise HTTPException(status_code=401, detail=result.message)
    user = result.user
    token = session_manager.create(
        user_id=str(user["id"]),
        email=user["email"],
        role=user.get("role", "user"),
    )
    return {
        "token": token,
        "user_id": str(user["id"]),
        "email": user["email"],
        "role": user.get("role", "user"),
    }


@app.post("/api/auth/logout")
async def logout(req: TokenOnlyRequest):
    session_manager.delete(req.token)
    return {"message": "Signed out."}


# ── Profile ────────────────────────────────────────────────────────────────────

@app.post("/api/profile/get")
async def get_profile(req: TokenOnlyRequest):
    session = _require_session(req.token)
    db_profile = load_user_profile(session["user_id"])
    merged = {**PROFILE_DEFAULTS, **{k: v for k, v in db_profile.items() if v is not None}}
    return {"profile": merged}


@app.post("/api/profile/save")
async def save_profile(req: ProfileRequest):
    session = _require_session(req.token)
    updates = req.model_dump(exclude={"token"}, exclude_none=True)
    db_profile = load_user_profile(session["user_id"])
    merged = {**PROFILE_DEFAULTS, **{k: v for k, v in db_profile.items() if v is not None}, **updates}
    save_user_profile(session["user_id"], merged)
    return {"profile": merged}


# ── Chat ───────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    session = _require_session(req.token)
    user_id = session["user_id"]

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

    try:
        result, usage = run_agent_tracked(agent, payload, req.model)
        response_text = result.get("output", "Sorry, I couldn't generate a response.")
        intermediate = result.get("intermediate_steps", [])

        tools_used = []
        sources = []
        pending_memories = []

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
                # Extract the fact from the observation string
                if "remember this" in obs_str.lower():
                    fact = str(tool_input.get("fact", ""))
                    if fact:
                        pending_memories.append(fact)

        return {
            "response": response_text,
            "tools_used": tools_used,
            "sources": sources,
            "pending_memories": pending_memories,
            "usage": {
                "total_tokens": usage.total_tokens,
                "estimated_cost_usd": round(usage.estimated_cost_usd, 6),
            },
        }

    except Exception as exc:
        fallback_tok = count_tokens(req.message, req.model)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "usage": {"total_tokens": fallback_tok},
            },
        )


# ── Memory (HITL) ──────────────────────────────────────────────────────────────

@app.post("/api/memories/get")
async def get_memories_endpoint(req: TokenOnlyRequest):
    session = _require_session(req.token)
    memories = get_memories(session["user_id"])
    return {"memories": memories}


@app.post("/api/memories/confirm")
async def confirm_memory(req: MemoryConfirmRequest):
    """Human-in-the-loop: user confirms a fact to persist long-term."""
    session = _require_session(req.token)
    save_memory(session["user_id"], req.memory)
    return {"message": "Memory saved.", "memory": req.memory}


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.post("/api/admin/stats")
async def admin_stats(req: TokenOnlyRequest):
    session = _require_session(req.token)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    stats = get_admin_dashboard_stats()
    stats["recent_logins"] = [dict(r) for r in stats["recent_logins"]]
    return stats


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.utcnow().isoformat()}
