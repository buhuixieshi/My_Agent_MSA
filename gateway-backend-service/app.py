import asyncio
import os
from typing import List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from scheduler_client import build_scheduler_client
from schemas import FrontendMessage, LoginRequest, LoginResponse
from sse_hub import SSEHub


APP_NAME = "gateway-backend-service"

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sse_hub = SSEHub()
scheduler_client = build_scheduler_client()


def build_session_id(user_id: str) -> str:
    return f"web_{user_id}"


def get_whitelist() -> List[str]:
    raw = os.getenv("USER_WHITELIST", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def ensure_allowed_user(user_id: str) -> None:
    whitelist = get_whitelist()
    if whitelist and user_id not in whitelist:
        raise HTTPException(status_code=403, detail="user is not in whitelist")


async def scheduler_event_consumer() -> None:
    subscriber_id = os.getenv("SUBSCRIBER_ID", "web-gateway-1")

    async for event in scheduler_client.subscribe_events(
        subscriber_id=subscriber_id,
        channels=["web"],
    ):
        await sse_hub.publish(event)


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(scheduler_event_consumer())


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": APP_NAME,
        "scheduler_client_mode": os.getenv("SCHEDULER_CLIENT_MODE", "grpc"),
        "scheduler_target": os.getenv(
            "SCHEDULER_GRPC_TARGET",
            "task-scheduler-service.agent.svc.cluster.local:5100",
        ),
    }


@app.post("/api/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user_id = req.user_id.strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="missing user_id")

    ensure_allowed_user(user_id)

    session_id = req.session_id or build_session_id(user_id)

    return LoginResponse(ok=True, user_id=user_id, session_id=session_id)


@app.post("/api/messages")
async def create_message(req: FrontendMessage):
    user_id = req.user_id.strip()
    content = req.content.strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="missing user_id")

    if not content:
        raise HTTPException(status_code=400, detail="missing content")

    ensure_allowed_user(user_id)

    if not req.session_id:
        req.session_id = build_session_id(user_id)

    result = await scheduler_client.create_task(req)

    if not result.ok:
        raise HTTPException(
            status_code=500,
            detail=result.error or "failed to create task",
        )

    return result.model_dump()


@app.get("/api/events")
async def events(
    user_id: str = Query(..., min_length=1),
    session_id: str = Query(default=""),
):
    ensure_allowed_user(user_id)

    async def stream():
        async for item in sse_hub.event_stream(user_id=user_id):
            yield item

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
