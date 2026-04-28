"""HPWD AI Agent — Unified Server (Static + LLM Demo).

Routes:
  /                    — public/index.html (redirect to roadmap-index)
  /<file>              — public/<file> (정적 파일)
  /demo                — LLM 데모 페이지 (암호 보호)
  /api/demo/auth       — POST 암호 검증
  /api/demo/health     — 데모 헬스체크
  /api/demo/scenarios  — 시나리오 목록
  /api/demo/run        — LLM 파이프라인 실행 (SSE, 인증 + rate limit)

Environment variables:
  ANTHROPIC_API_KEY    — Anthropic API 키 (필수, 데모용)
  DEMO_PASSWORD        — 데모 접근 암호 (필수)
  PORT                 — 서버 포트 (Railway 자동 주입, 기본 8080)
  DEMO_DAILY_LIMIT     — 일일 총 LLM 호출 제한 (기본 100)
  DEMO_PER_MIN_LIMIT   — IP당 분당 호출 제한 (기본 3)
"""
import os
import json
import time
import asyncio
import secrets
import hashlib
from pathlib import Path
from collections import defaultdict, deque
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, Cookie
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from anthropic import Anthropic, APIError

# Local imports
import sys
sys.path.insert(0, str(Path(__file__).parent / "demo"))
from tools import TOOL_DEFINITIONS, execute_tool
from prompts import (
    INTERPRETER_SYSTEM_PROMPT,
    MAIN_AGENT_SYSTEM_PROMPT,
    get_explainer_prompt,
)


# ============================================================
# Config
# ============================================================
ROOT_DIR = Path(__file__).parent
PUBLIC_DIR = ROOT_DIR / "public"
LLM_MODEL = "claude-sonnet-4-5-20250929"

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")
DAILY_LIMIT = int(os.environ.get("DEMO_DAILY_LIMIT", "100"))
PER_MIN_LIMIT = int(os.environ.get("DEMO_PER_MIN_LIMIT", "3"))

client = Anthropic(api_key=API_KEY) if API_KEY else None
app = FastAPI(title="HPWD AI Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Auth tokens (in-memory, ephemeral on Railway redeploy)
AUTH_TOKENS: dict[str, float] = {}
TOKEN_TTL = 8 * 3600  # 8시간

# Rate limit state
ip_calls: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
daily_state = {"count": 0, "reset_at": 0}


# ============================================================
# Auth
# ============================================================
def is_authenticated(token: str | None) -> bool:
    if not token:
        return False
    expiry = AUTH_TOKENS.get(token)
    if expiry is None:
        return False
    if time.time() > expiry:
        AUTH_TOKENS.pop(token, None)
        return False
    return True


def issue_token() -> str:
    token = secrets.token_urlsafe(32)
    AUTH_TOKENS[token] = time.time() + TOKEN_TTL
    return token


def check_rate_limit(ip: str) -> tuple[bool, str]:
    now = time.time()
    if now > daily_state["reset_at"]:
        daily_state["count"] = 0
        daily_state["reset_at"] = now + 86400
    if daily_state["count"] >= DAILY_LIMIT:
        return False, f"오늘의 일일 호출 한도({DAILY_LIMIT}회)를 초과했습니다. 내일 다시 시도하세요."
    calls = ip_calls[ip]
    cutoff = now - 60
    while calls and calls[0] < cutoff:
        calls.popleft()
    if len(calls) >= PER_MIN_LIMIT:
        return False, f"분당 호출 한도({PER_MIN_LIMIT}회)를 초과했습니다. 잠시 후 다시 시도하세요."
    calls.append(now)
    daily_state["count"] += 1
    return True, ""


# ============================================================
# Models
# ============================================================
class AuthRequest(BaseModel):
    password: str


class RunRequest(BaseModel):
    user_message: str
    audience: str = "expert"
    max_tool_iterations: int = 6


# ============================================================
# Scenarios
# ============================================================
SCENARIOS = [
    {
        "id": "sc_diagnose",
        "title": "1. 진단 — 빨래가 안 말라요",
        "description": "증상 입력 → 자동 진단 → 원인 → 조치 권장",
        "user_message": "HPWD-24-EU 모델인데 빨래가 안 말라. 왜 그런 거지?",
    },
    {
        "id": "sc_simulate",
        "title": "2. 시뮬 — 응축기 UA 14% 변경 시?",
        "description": "What-if 변경 시뮬레이션",
        "user_message": "HPWD-24-EU에서 응축기 UA를 14% 늘리면 SMER이 어떻게 변할까?",
    },
    {
        "id": "sc_query",
        "title": "3. 조회 — 시험 보고서 해석",
        "description": "단순 데이터 조회 + 의미 해석",
        "user_message": "HPWD-24-EU 최근 시험 결과 보여줘. 통과했어?",
    },
]


# ============================================================
# Pipeline (SSE)
# ============================================================
def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_pipeline(user_message: str, audience: str, max_iter: int) -> AsyncIterator[str]:
    if client is None:
        yield sse_event("error", {
            "step": "init",
            "message": "ANTHROPIC_API_KEY 미설정 — Railway 환경변수에 추가 필요"
        })
        yield sse_event("done", {})
        return

    try:
        # ① Interpreter
        yield sse_event("step_start", {
            "step": 1, "name": "Interpreter",
            "title": "① Interpreter — 의도 정형화",
            "description": "자연어 질문을 정형 JSON 쿼리로 변환"
        })

        interpreter_response = await asyncio.to_thread(
            client.messages.create,
            model=LLM_MODEL,
            max_tokens=400,
            system=INTERPRETER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        interpreter_text = "".join(b.text for b in interpreter_response.content if b.type == "text").strip()

        try:
            cleaned = interpreter_text.replace("```json", "").replace("```", "").strip()
            interpreter_result = json.loads(cleaned)
        except json.JSONDecodeError:
            interpreter_result = {
                "intent": "ambiguous",
                "symptom": user_message,
                "raw": interpreter_text,
                "parse_error": True,
            }

        yield sse_event("step_data", {"step": 1, "data": interpreter_result})
        yield sse_event("step_done", {"step": 1})

        if interpreter_result.get("needs_clarification"):
            yield sse_event("clarification_needed", {
                "question": interpreter_result.get("clarification_question", "추가 정보가 필요합니다"),
                "current_understanding": interpreter_result.get("symptom", ""),
            })
            yield sse_event("done", {})
            return

        # ② RAG
        yield sse_event("step_start", {
            "step": 2, "name": "RAG",
            "title": "② RAG — 사내 자료 검색 (사전)",
            "description": "Interpreter가 추출한 키워드로 의미 검색"
        })
        keywords = interpreter_result.get("search_keywords", [])
        search_query = " ".join(keywords) if keywords else interpreter_result.get("symptom", user_message)
        rag_result = execute_tool("search_documents", {"query": search_query})
        yield sse_event("step_data", {"step": 2, "data": rag_result})
        yield sse_event("step_done", {"step": 2})

        # ③ Tool-use Agent
        yield sse_event("step_start", {
            "step": 3, "name": "Tool-use Agent",
            "title": "③ 외부 LLM API + Tool-use — 도구 호출형 답변",
            "description": "LLM이 시뮬·DB·최적화 도구를 직접 호출"
        })

        formatted_context = f"""사용자 원본 질문: "{user_message}"

Interpreter 분석 결과:
{json.dumps(interpreter_result, ensure_ascii=False, indent=2)}

사전 RAG 검색 결과 (키워드: {search_query}):
{json.dumps(rag_result, ensure_ascii=False, indent=2)}

위 컨텍스트를 바탕으로 추가 도구(query_components, run_simulation, suggest_optimization)를 호출해 답변을 완성하세요."""

        messages = [{"role": "user", "content": formatted_context}]
        tool_history = []
        final_text = ""
        text_blocks = []

        for iteration in range(max_iter):
            response = await asyncio.to_thread(
                client.messages.create,
                model=LLM_MODEL,
                max_tokens=2000,
                system=MAIN_AGENT_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b.text for b in response.content if b.type == "text"]

            if text_blocks:
                yield sse_event("agent_text", {"iteration": iteration + 1, "text": "\n".join(text_blocks)})

            if not tool_uses:
                final_text = "\n".join(text_blocks)
                yield sse_event("step_done", {"step": 3, "iterations": iteration + 1})
                break

            tool_results_blocks = []
            for tu in tool_uses:
                yield sse_event("tool_call", {
                    "iteration": iteration + 1,
                    "tool_name": tu.name,
                    "tool_input": tu.input,
                    "tool_use_id": tu.id,
                })
                result = await asyncio.to_thread(execute_tool, tu.name, tu.input)
                tool_history.append({"tool": tu.name, "input": tu.input, "result": result})
                yield sse_event("tool_result", {
                    "tool_name": tu.name,
                    "tool_use_id": tu.id,
                    "result": result,
                })
                tool_results_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            messages.append({"role": "user", "content": tool_results_blocks})
        else:
            final_text = "(최대 반복 초과)"
            yield sse_event("step_done", {"step": 3, "iterations": max_iter, "warning": "max iterations"})

        # ④ Explainer
        yield sse_event("step_start", {
            "step": 4, "name": "Explainer",
            "title": "④ Explainer — 답변 형식화",
            "description": f"답변을 '{audience}' 형식에 맞게 가공"
        })

        explainer_input = f"""원본 사용자 질문: "{user_message}"

Agent 최종 답변:
{final_text or (text_blocks[0] if text_blocks else '(답변 없음)')}

수집된 데이터 (도구 호출 결과):
{json.dumps(tool_history, ensure_ascii=False, indent=2)[:3000]}

위 내용을 사용자 표시 형식으로 정리하세요."""

        explainer_response = await asyncio.to_thread(
            client.messages.create,
            model=LLM_MODEL,
            max_tokens=1500,
            system=get_explainer_prompt(audience),
            messages=[{"role": "user", "content": explainer_input}],
        )
        explainer_text = "".join(b.text for b in explainer_response.content if b.type == "text").strip()

        try:
            cleaned = explainer_text.replace("```json", "").replace("```", "").strip()
            explainer_result = json.loads(cleaned)
        except json.JSONDecodeError:
            explainer_result = {"title": "답변 형식화 실패", "raw_text": explainer_text, "parse_error": True}

        yield sse_event("step_data", {"step": 4, "data": explainer_result})
        yield sse_event("step_done", {"step": 4})

        # ⑤ Logger (Railway에서는 ephemeral, 발표용으로만 의미 있음)
        yield sse_event("step_start", {
            "step": 5, "name": "Logger",
            "title": "⑤ 로그 저장 — Phase 2 학습 데이터",
            "description": "대화 + 도구 호출 + 답변 전수 저장"
        })
        log_entry = {
            "timestamp": time.time(),
            "user_message": user_message,
            "tool_call_count": len(tool_history),
        }
        try:
            log_file = ROOT_DIR / "demo_logs.jsonl"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            log_size = log_file.stat().st_size
        except Exception:
            log_size = -1

        yield sse_event("step_data", {
            "step": 5,
            "data": {
                "saved": True,
                "log_size": log_size,
                "tool_call_count": len(tool_history),
                "note": "Phase 2 자체 sLLM 학습 데이터셋에 추가됨"
            },
        })
        yield sse_event("step_done", {"step": 5})

        yield sse_event("final", {
            "interpreter": interpreter_result,
            "rag_documents": rag_result,
            "tool_calls": tool_history,
            "explainer": explainer_result,
        })

    except APIError as e:
        yield sse_event("error", {"step": "llm_api", "message": f"LLM API 에러: {e}"})
    except Exception as e:
        import traceback
        yield sse_event("error", {
            "step": "pipeline",
            "message": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(limit=3),
        })

    yield sse_event("done", {})


# ============================================================
# API endpoints
# ============================================================
@app.get("/api/demo/health")
async def health(demo_auth: str | None = Cookie(None)):
    return {
        "status": "ok",
        "llm_configured": client is not None,
        "password_set": bool(DEMO_PASSWORD),
        "authenticated": is_authenticated(demo_auth),
        "model": LLM_MODEL,
        "tool_count": len(TOOL_DEFINITIONS),
        "daily_limit": DAILY_LIMIT,
        "daily_used": daily_state["count"],
        "per_min_limit": PER_MIN_LIMIT,
    }


@app.get("/api/demo/scenarios")
async def scenarios():
    return {"scenarios": SCENARIOS}


@app.post("/api/demo/auth")
async def authenticate(req: AuthRequest):
    if not DEMO_PASSWORD:
        raise HTTPException(503, "DEMO_PASSWORD 미설정")
    expected = hashlib.sha256(DEMO_PASSWORD.encode()).digest()
    actual = hashlib.sha256(req.password.encode()).digest()
    if not secrets.compare_digest(expected, actual):
        raise HTTPException(401, "암호가 올바르지 않습니다")
    token = issue_token()
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key="demo_auth",
        value=token,
        max_age=TOKEN_TTL,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response


@app.post("/api/demo/run")
async def run(req: RunRequest, request: Request, demo_auth: str | None = Cookie(None)):
    if not is_authenticated(demo_auth):
        raise HTTPException(401, "인증 필요. /demo 페이지에서 암호 입력")
    ip = request.client.host if request.client else "unknown"
    ok, reason = check_rate_limit(ip)
    if not ok:
        raise HTTPException(429, reason)
    return StreamingResponse(
        stream_pipeline(req.user_message, req.audience, req.max_tool_iterations),
        media_type="text/event-stream",
    )


# ============================================================
# Pages
# ============================================================
@app.get("/demo")
async def demo_page():
    demo_html = ROOT_DIR / "demo" / "index.html"
    if not demo_html.exists():
        raise HTTPException(404, "demo/index.html missing")
    return FileResponse(demo_html)


@app.get("/")
async def root():
    index = PUBLIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(404, "public/index.html missing")


# Static file serving (마지막에 마운트해서 위 라우트들이 우선 매칭되게)
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 HPWD AI Agent server on port {port}")
    print(f"   LLM: {'configured' if client else 'NOT CONFIGURED'}")
    print(f"   Password: {'set' if DEMO_PASSWORD else 'NOT SET'}")
    print(f"   Limits: {PER_MIN_LIMIT}/min, {DAILY_LIMIT}/day")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
