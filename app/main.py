"""FastAPI application for SHL Assessment Recommender."""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from app.config import configure_logging
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.policy import build_response

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SHL Assessment Recommender",
    description="Conversational SHL Individual Test Solutions recommender API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.messages:
        raise HTTPException(status_code=422, detail="messages cannot be empty")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    response = build_response(messages)
    return response
