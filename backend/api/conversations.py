from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ── Persist to a JSON file so conversations survive server restarts ──────
_CONVERSATIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "conversations"
_CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


def _user_file(email: str) -> Path:
    """Return the JSON file path for a given user (safe filename from email)."""
    safe = email.replace("@", "_at_").replace(".", "_dot_")
    return _CONVERSATIONS_DIR / f"{safe}.json"


def _load_user_conversations(email: str) -> dict[str, dict[str, Any]]:
    """Load a user's conversations from their JSON file on disk."""
    fp = _user_file(email)
    if not fp.exists():
        return {}
    try:
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_user_conversations(email: str, data: dict[str, dict[str, Any]]) -> None:
    """Write a user's conversations to their JSON file on disk."""
    fp = _user_file(email)
    try:
        with fp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str, indent=2)
    except OSError:
        pass  # Best-effort persistence — in-memory copy still works.


# ── In-memory cache keyed by email → { id → raw_dict } ──────────────────
# Loaded from disk on first access; written back on every mutation.
_CONVERSATIONS_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def _get_records(email: str) -> dict[str, dict[str, Any]]:
    """Get or load the user's conversation dict (lazy-load from disk)."""
    if email not in _CONVERSATIONS_CACHE:
        _CONVERSATIONS_CACHE[email] = _load_user_conversations(email)
    return _CONVERSATIONS_CACHE[email]


def _put_record(email: str, record: dict[str, Any]) -> None:
    """Save one record and persist to disk."""
    records = _get_records(email)
    records[record["id"]] = record
    _save_user_conversations(email, records)


def _remove_record(email: str, record_id: str) -> None:
    """Delete one record and persist to disk."""
    records = _get_records(email)
    records.pop(record_id, None)
    _save_user_conversations(email, records)


def _clear_records(email: str) -> None:
    """Delete all records for a user and persist to disk."""
    _CONVERSATIONS_CACHE[email] = {}
    _save_user_conversations(email, {})


# ── Pydantic models ─────────────────────────────────────────────────────

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
    productName: str | None = None
    quantity: str | None = None
    unit: str | None = None
    brand: str | None = None
    structuredCategory: str | None = None
    structuredCountry: str | None = None
    structuredCerts: str | None = None


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
    filters: dict[str, str] = Field(default_factory=dict)
    restore: ConversationRestore | None = None
    requestSnapshot: dict[str, Any] | None = Field(default=None, description="Snapshot of the full request payload")
    resultsSnapshot: list[dict[str, Any]] | None = Field(default=None, description="Full search results for auto-restore on reopen")
    resultCount: int = 0
    candidateNames: list[str] = Field(default_factory=list)


class ConversationRecord(NewConversation):
    id: str
    timestamp: int
    feedback: FeedbackRecord | None = None


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[ConversationRecord])
async def list_conversations(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    range: str = "30d",
) -> list[ConversationRecord]:
    """List conversations for the current user, with optional time-range filter.

    Range: 7d, 30d, 1y, all  (default 30d).
    """
    now_ms = _now_ms()
    cutoff_ms: int | None = None
    if range == "7d":
        cutoff_ms = now_ms - 7 * 24 * 60 * 60 * 1000
    elif range == "30d":
        cutoff_ms = now_ms - 30 * 24 * 60 * 60 * 1000
    elif range == "1y":
        cutoff_ms = now_ms - 365 * 24 * 60 * 60 * 1000
    # "all" -> no cutoff

    records = _get_records(current_user.email)
    sorted_records = sorted(
        (r for r in records.values()
         if cutoff_ms is None or r.get("timestamp", 0) >= cutoff_ms),
        key=lambda r: r.get("timestamp", 0),
        reverse=True,
    )
    return [ConversationRecord(**r) for r in sorted_records]


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
    _put_record(current_user.email, record.model_dump())
    return record


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_conversations(
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    _clear_records(current_user.email)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.patch("/{id}/feedback", response_model=ConversationRecord)
async def attach_feedback(
    id: str,
    req: FeedbackRecord,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ConversationRecord:
    records = _get_records(current_user.email)
    raw = records.get(id)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Conversation not found"},
        )
    raw["feedback"] = req.model_dump()
    _save_user_conversations(current_user.email, records)
    return ConversationRecord(**raw)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    id: str,
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    _remove_record(current_user.email, id)
    response.status_code = status.HTTP_204_NO_CONTENT
