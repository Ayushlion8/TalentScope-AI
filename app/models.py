"""Pydantic models for request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: list[str] = Field(default_factory=list)
    remote_testing: bool = False
    adaptive_irt: bool = False
    duration_minutes: int | None = None
    description: str = ""
    job_levels: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    end_of_conversation: bool = False


class HealthResponse(BaseModel):
    status: str
