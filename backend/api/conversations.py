from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ── Local fallback for development only ───────────────────────────────────
# Production should set DATABASE_URL; then records are stored in Postgres/Supabase.
_CONVERSATIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "conversations"
_CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
_CONVERSATIONS_CACHE: dict[str, dict[str, dict[str, Any]]] = {}
_DB_READY = False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _user_file(email: str) -> Path:
    safe = email.replace("@", "_at_").replace(".", "_dot_")
    return _CONVERSATIONS_DIR / f"{safe}.json"


def _load_user_conversations(email: str) -> dict[str, dict[str, Any]]:
    fp = _user_file(email)
    if not fp.exists():
        return {}
    try:
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_user_conversations(email: str, data: dict[str, dict[str, Any]]) -> None:
    fp = _user_file(email)
    tmp = fp.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str, indent=2)
    tmp.replace(fp)


def _get_local_records(email: str) -> dict[str, dict[str, Any]]:
    if email not in _CONVERSATIONS_CACHE:
        _CONVERSATIONS_CACHE[email] = _load_user_conversations(email)
    return _CONVERSATIONS_CACHE[email]


def _database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.strip() if value and value.strip() else None


def _db_conn():
    database_url = _database_url()
    if not database_url:
        return None
    return psycopg2.connect(database_url)


def _ensure_table(conn) -> None:
    global _DB_READY
    if _DB_READY:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_history (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                module TEXT NOT NULL CHECK (module IN ('sourcing', 'comparison')),
                query TEXT NOT NULL,
                filters JSONB NOT NULL DEFAULT '{}',
                restore JSONB,
                request_snapshot JSONB,
                results_snapshot JSONB,
                result_count INTEGER NOT NULL DEFAULT 0,
                candidate_names JSONB NOT NULL DEFAULT '[]',
                feedback JSONB,
                timestamp_ms BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_history_user_time
            ON conversation_history (user_email, timestamp_ms DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_history_user_module_time
            ON conversation_history (user_email, module, timestamp_ms DESC)
            """
        )
    conn.commit()
    _DB_READY = True


def _row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "module": row["module"],
        "query": row["query"],
        "filters": row.get("filters") or {},
        "restore": row.get("restore"),
        "requestSnapshot": row.get("request_snapshot"),
        "resultsSnapshot": row.get("results_snapshot"),
        "resultCount": row.get("result_count") or 0,
        "candidateNames": row.get("candidate_names") or [],
        "timestamp": row.get("timestamp_ms") or _now_ms(),
        "feedback": row.get("feedback"),
    }


def _range_cutoff_ms(range_value: str) -> int | None:
    now = _now_ms()
    if range_value == "7d":
        return now - 7 * 24 * 60 * 60 * 1000
    if range_value == "30d":
        return now - 30 * 24 * 60 * 60 * 1000
    if range_value == "1y":
        return now - 365 * 24 * 60 * 60 * 1000
    return None


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
    requestSnapshot: dict[str, Any] | None = None
    resultsSnapshot: list[dict[str, Any]] | None = None
    resultCount: int = 0
    candidateNames: list[str] = Field(default_factory=list)


class ConversationRecord(NewConversation):
    id: str
    timestamp: int
    feedback: FeedbackRecord | None = None


def _local_list(email: str, range_value: str) -> list[ConversationRecord]:
    cutoff = _range_cutoff_ms(range_value)
    records = _get_local_records(email)
    sorted_records = sorted(
        (r for r in records.values() if cutoff is None or int(r.get("timestamp", 0)) >= cutoff),
        key=lambda r: int(r.get("timestamp", 0)),
        reverse=True,
    )
    return [ConversationRecord(**r) for r in sorted_records]


def _local_put(email: str, record: ConversationRecord) -> None:
    records = _get_local_records(email)
    records[record.id] = record.model_dump()
    _save_user_conversations(email, records)


def _local_clear(email: str) -> None:
    _CONVERSATIONS_CACHE[email] = {}
    _save_user_conversations(email, {})


@router.get("", response_model=list[ConversationRecord])
async def list_conversations(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    range: Literal["7d", "30d", "1y", "all"] = Query("30d"),
) -> list[ConversationRecord]:
    conn = _db_conn()
    if conn is None:
        return _local_list(current_user.email, range)
    try:
        _ensure_table(conn)
        cutoff = _range_cutoff_ms(range)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if cutoff is None:
                cur.execute(
                    """
                    SELECT * FROM conversation_history
                    WHERE user_email = %s
                    ORDER BY timestamp_ms DESC
                    """,
                    (current_user.email,),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM conversation_history
                    WHERE user_email = %s AND timestamp_ms >= %s
                    ORDER BY timestamp_ms DESC
                    """,
                    (current_user.email, cutoff),
                )
            return [ConversationRecord(**_row_to_record(dict(row))) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("", response_model=ConversationRecord, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: NewConversation,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ConversationRecord:
    record = ConversationRecord(**req.model_dump(), id=uuid4().hex, timestamp=_now_ms())
    conn = _db_conn()
    if conn is None:
        _local_put(current_user.email, record)
        return record
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_history (
                    id, user_email, module, query, filters, restore,
                    request_snapshot, results_snapshot, result_count,
                    candidate_names, feedback, timestamp_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.id,
                    current_user.email,
                    record.module,
                    record.query,
                    Json(record.filters),
                    Json(record.restore.model_dump() if record.restore else None),
                    Json(record.requestSnapshot),
                    Json(record.resultsSnapshot),
                    record.resultCount,
                    Json(record.candidateNames),
                    Json(record.feedback.model_dump() if record.feedback else None),
                    record.timestamp,
                ),
            )
        conn.commit()
        return record
    finally:
        conn.close()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_conversations(
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    conn = _db_conn()
    if conn is None:
        _local_clear(current_user.email)
    else:
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversation_history WHERE user_email = %s", (current_user.email,))
            conn.commit()
        finally:
            conn.close()
    response.status_code = status.HTTP_204_NO_CONTENT


@router.patch("/{id}/feedback", response_model=ConversationRecord)
async def attach_feedback(
    id: str,
    req: FeedbackRecord,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ConversationRecord:
    conn = _db_conn()
    if conn is None:
        records = _get_local_records(current_user.email)
        raw = records.get(id)
        if raw is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Conversation not found"})
        raw["feedback"] = req.model_dump()
        _save_user_conversations(current_user.email, records)
        return ConversationRecord(**raw)
    try:
        _ensure_table(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE conversation_history
                SET feedback = %s, updated_at = now()
                WHERE id = %s AND user_email = %s
                RETURNING *
                """,
                (Json(req.model_dump()), id, current_user.email),
            )
            row = cur.fetchone()
        conn.commit()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Conversation not found"})
        return ConversationRecord(**_row_to_record(dict(row)))
    finally:
        conn.close()


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    id: str,
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    conn = _db_conn()
    if conn is None:
        records = _get_local_records(current_user.email)
        records.pop(id, None)
        _save_user_conversations(current_user.email, records)
    else:
        try:
            _ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversation_history WHERE id = %s AND user_email = %s", (id, current_user.email))
            conn.commit()
        finally:
            conn.close()
    response.status_code = status.HTTP_204_NO_CONTENT
