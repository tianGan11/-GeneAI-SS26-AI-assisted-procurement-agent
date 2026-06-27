"""
Sourcing API — supplier discovery.

Optimization over the original:
  - Added auth protection via Depends(get_current_user) so the endpoint
    requires a valid Bearer token, matching the openapi.yaml contract.
  - Added asynchronous search jobs so long-running live web research can expose
    real progress to the frontend instead of looking frozen behind one request.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Annotated, AsyncIterator, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/sourcing", tags=["sourcing"])


class StructuredFields(BaseModel):
    productName: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    certifications: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    structured: Optional[StructuredFields] = None


class SearchJobEvent(BaseModel):
    timestamp: int
    phase: str
    message: str
    progress: int


class SearchJobResponse(BaseModel):
    jobId: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    step: str
    events: list[SearchJobEvent]
    intent: dict | None = None
    results: list[dict] = Field(default_factory=list)
    error: str | None = None


class _SearchJobState(SearchJobResponse):
    owner: str


_SEARCH_JOBS: dict[str, _SearchJobState] = {}
_MAX_JOBS = 100


def _now_ms() -> int:
    return int(time.time() * 1000)


def _public_job(job: _SearchJobState) -> SearchJobResponse:
    return SearchJobResponse(**job.model_dump(exclude={"owner"}))


def _append_event(job: _SearchJobState, phase: str, message: str, progress: int) -> None:
    progress = max(0, min(100, int(progress)))
    job.progress = max(job.progress, progress)
    job.step = message
    job.events.append(
        SearchJobEvent(
            timestamp=_now_ms(),
            phase=phase,
            message=message,
            progress=job.progress,
        )
    )


def _prune_jobs() -> None:
    if len(_SEARCH_JOBS) <= _MAX_JOBS:
        return
    oldest = sorted(
        _SEARCH_JOBS.items(),
        key=lambda item: item[1].events[0].timestamp if item[1].events else 0,
    )
    for job_id, _ in oldest[: len(_SEARCH_JOBS) - _MAX_JOBS]:
        _SEARCH_JOBS.pop(job_id, None)


async def _run_search_job(job_id: str, query: str, agent: object, structured: Optional[dict] = None) -> None:
    job = _SEARCH_JOBS[job_id]
    job.status = "running"
    _append_event(job, "queued", "已接收供应商研究任务，Agent 正在启动采购需求分析流程...", 5)

    def progress(phase: str, message: str, percent: int) -> None:
        _append_event(job, phase, message, percent)

    try:
        try:
            result = await agent.search_suppliers(query, progress=progress, structured=structured)  # type: ignore[attr-defined]
        except TypeError as exc:
            # Backward-compatible with tests/older agent objects that have not
            # added the optional structured= keyword yet. Real agent errors are
            # still surfaced by retrying only this exact compatibility case.
            if "structured" not in str(exc):
                raise
            result = await agent.search_suppliers(query, progress=progress)  # type: ignore[attr-defined]
        job.intent = result.get("intent")
        job.results = result.get("results", [])
        job.status = "completed"
        _append_event(job, "completed", "候选名单已准备就绪，可以开始查看结果了。", 100)
    except Exception as exc:  # pragma: no cover - exact production errors vary
        job.status = "failed"
        job.error = str(exc)
        _append_event(job, "failed", f"研究过程遇到了问题：{exc}。请尝试调整需求描述后重试。", max(job.progress, 5))


def reset_search_jobs_for_tests() -> None:
    _SEARCH_JOBS.clear()


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_search_job_events(job_id: str, owner: str) -> AsyncIterator[str]:
    """Yield job updates as Server-Sent Events until the job reaches a terminal state."""
    last_event_count = -1
    last_status: str | None = None
    while True:
        job = _SEARCH_JOBS.get(job_id)
        if job is None or job.owner != owner:
            yield _format_sse("error", {"code": "NOT_FOUND", "message": "Search job not found"})
            return

        event_count = len(job.events)
        if event_count != last_event_count or job.status != last_status:
            yield _format_sse("job", _public_job(job).model_dump())
            last_event_count = event_count
            last_status = job.status

        if job.status in {"completed", "failed"}:
            yield _format_sse("done", _public_job(job).model_dump())
            return

        await asyncio.sleep(1)


@router.post("/search")
async def search(
    req: SearchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """
    POST /api/sourcing/search — match openapi.yaml spec.

    Protected: requires Authorization: Bearer *** header.
    """
    structured = req.structured.model_dump() if req.structured else None
    try:
        return await request.app.state.agent.search_suppliers(req.query, structured=structured)
    except TypeError as exc:
        if "structured" not in str(exc):
            raise
        return await request.app.state.agent.search_suppliers(req.query)


@router.post("/search-jobs", response_model=SearchJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_search_job(
    req: SearchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> SearchJobResponse:
    """Create an asynchronous supplier-research job and return immediately."""
    _prune_jobs()
    job_id = uuid4().hex
    job = _SearchJobState(
        jobId=job_id,
        owner=current_user.email,
        status="queued",
        progress=0,
        step="Queued",
        events=[],
        intent=None,
        results=[],
        error=None,
    )
    _append_event(job, "queued", "Queued supplier research job", 0)
    _SEARCH_JOBS[job_id] = job
    asyncio.create_task(_run_search_job(job_id, req.query, request.app.state.agent, structured=req.structured.model_dump() if req.structured else None))
    return _public_job(job)


@router.get("/search-jobs/{job_id}", response_model=SearchJobResponse)
async def get_search_job(
    job_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> SearchJobResponse:
    """Poll a supplier-research job created by POST /search-jobs."""
    job = _SEARCH_JOBS.get(job_id)
    if job is None or job.owner != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Search job not found"},
        )
    return _public_job(job)


@router.get("/search-jobs/{job_id}/events")
async def stream_search_job_events(
    job_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> StreamingResponse:
    """Stream supplier-research job progress as SSE; clients may fall back to polling."""
    job = _SEARCH_JOBS.get(job_id)
    if job is None or job.owner != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Search job not found"},
        )
    return StreamingResponse(
        _stream_search_job_events(job_id, current_user.email),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
