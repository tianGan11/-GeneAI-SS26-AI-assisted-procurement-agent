from __future__ import annotations

import time
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class FactorWeights(BaseModel):
    price: int
    delivery: int
    rating: int


class ConversationRestore(BaseModel):
    query: str
    minPrice: str | None = None
    maxPrice: str | None = None
    deliveryTime: Literal["unlimited", "within3", "within7"] | None = None
    weights: FactorWeights | None = None


class FeedbackRecord(BaseModel):
    chosenName: str
    quality: int = Field(ge=0, le=5)
    logistics: int = Field(ge=0, le=5)
    priceSatisfaction: int = Field(ge=0, le=5)
    service: int = Field(ge=0, le=5)
    comment: str
    submittedAt: int


class NewConversation(BaseModel):
    module: Literal["sourcing", "comparison"]
    query: str
    filters: dict[str, str]
    restore: ConversationRestore | None = None
    resultCount: int
    candidateNames: list[str]


class ConversationRecord(NewConversation):
    id: str
    timestamp: int
    feedback: FeedbackRecord | None = None


MOCK_CONVERSATIONS: dict[str, dict[str, ConversationRecord]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


@router.get("", response_model=list[ConversationRecord])
async def list_conversations(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> list[ConversationRecord]:
    records = MOCK_CONVERSATIONS.get(current_user.email, {})
    return sorted(records.values(), key=lambda record: record.timestamp, reverse=True)


@router.post("", response_model=ConversationRecord, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: NewConversation,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ConversationRecord:
    record = ConversationRecord(
        **req.model_dump(),
        id=uuid4().hex,
        timestamp=_now_ms(),
    )
    MOCK_CONVERSATIONS.setdefault(current_user.email, {})[record.id] = record
    return record


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_conversations(
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    MOCK_CONVERSATIONS[current_user.email] = {}
    response.status_code = status.HTTP_204_NO_CONTENT


@router.patch("/{id}/feedback", response_model=ConversationRecord)
async def attach_feedback(
    id: str,
    req: FeedbackRecord,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ConversationRecord:
    records = MOCK_CONVERSATIONS.get(current_user.email, {})
    record = records.get(id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Conversation not found"},
        )
    updated = record.model_copy(update={"feedback": req})
    records[id] = updated
    return updated


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    id: str,
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    MOCK_CONVERSATIONS.get(current_user.email, {}).pop(id, None)
    response.status_code = status.HTTP_204_NO_CONTENT
