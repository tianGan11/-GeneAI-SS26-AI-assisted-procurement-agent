"""
Comparison API — standard-product quote benchmarking.

Optimization over the original:
  - Added auth protection via Depends(get_current_user) so the endpoint
    requires a valid Bearer token, matching the openapi.yaml contract.
  - Added asynchronous comparison jobs so long-running Agent analysis can expose
    real progress to the frontend, mirroring the supplier sourcing module.
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


router = APIRouter(prefix="/api/comparison", tags=["comparison"])


class FactorWeights(BaseModel):
    price: int = 40
    delivery: int = 35
    rating: int = 25


class ComparisonSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    deliveryTime: Optional[str] = None
    weights: Optional[FactorWeights] = None


class ComparisonJobEvent(BaseModel):
    timestamp: int
    phase: str
    message: str
    progress: int


class ComparisonJobResponse(BaseModel):
    jobId: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    step: str
    events: list[ComparisonJobEvent]
    intent: dict | None = None
    results: list[dict] = Field(default_factory=list)
    error: str | None = None


class _ComparisonJobState(ComparisonJobResponse):
    owner: str


_COMPARISON_JOBS: dict[str, _ComparisonJobState] = {}
_MAX_JOBS = 100


def _now_ms() -> int:
    return int(time.time() * 1000)


def _public_job(job: _ComparisonJobState) -> ComparisonJobResponse:
    return ComparisonJobResponse(**job.model_dump(exclude={"owner"}))


def _append_event(job: _ComparisonJobState, phase: str, message: str, progress: int) -> None:
    progress = max(0, min(100, int(progress)))
    job.progress = max(job.progress, progress)
    job.step = message
    job.events.append(
        ComparisonJobEvent(
            timestamp=_now_ms(),
            phase=phase,
            message=message,
            progress=job.progress,
        )
    )


def _prune_jobs() -> None:
    if len(_COMPARISON_JOBS) <= _MAX_JOBS:
        return
    oldest = sorted(
        _COMPARISON_JOBS.items(),
        key=lambda item: item[1].events[0].timestamp if item[1].events else 0,
    )
    for job_id, _ in oldest[: len(_COMPARISON_JOBS) - _MAX_JOBS]:
        _COMPARISON_JOBS.pop(job_id, None)


async def _run_comparison_job(job_id: str, req: ComparisonSearchRequest, agent: object) -> None:
    job = _COMPARISON_JOBS[job_id]
    job.status = "running"
    _append_event(job, "queued", "已接收标准品比价任务，Agent 正在启动采购报价分析流程...", 5)

    def progress(phase: str, message: str, percent: int) -> None:
        _append_event(job, phase, message, percent)

    try:
        try:
            result = await agent.search_quotes(  # type: ignore[attr-defined]
                req.query,
                min_price=req.minPrice,
                max_price=req.maxPrice,
                delivery_time=req.deliveryTime,
                weights=req.weights.model_dump() if req.weights else None,
                progress=progress,
            )
        except TypeError as exc:
            if "progress" not in str(exc) and "weights" not in str(exc):
                raise
            result = await agent.search_quotes(  # type: ignore[attr-defined]
                req.query,
                min_price=req.minPrice,
                max_price=req.maxPrice,
                delivery_time=req.deliveryTime,
            )
        job.intent = result.get("intent")
        job.results = result.get("results", [])
        job.status = "completed"
        _append_event(job, "completed", "标准品比价表已准备就绪，可以查看推荐结果了。", 100)
    except Exception as exc:  # pragma: no cover - exact production errors vary
        job.status = "failed"
        job.error = str(exc)
        _append_event(job, "failed", f"比价分析遇到了问题：{exc}。请尝试调整需求描述或过滤条件后重试。", max(job.progress, 5))


def reset_comparison_jobs_for_tests() -> None:
    _COMPARISON_JOBS.clear()


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_comparison_job_events(job_id: str, owner: str) -> AsyncIterator[str]:
    last_event_count = -1
    last_status: str | None = None
    while True:
        job = _COMPARISON_JOBS.get(job_id)
        if job is None or job.owner != owner:
            yield _format_sse("error", {"code": "NOT_FOUND", "message": "Comparison job not found"})
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
    req: ComparisonSearchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """
    POST /api/comparison/search — match openapi.yaml spec.

    Protected: requires Authorization: Bearer header.
    """
    try:
        return await request.app.state.agent.search_quotes(
            req.query,
            min_price=req.minPrice,
            max_price=req.maxPrice,
            delivery_time=req.deliveryTime,
            weights=req.weights.model_dump() if req.weights else None,
        )
    except TypeError as exc:
        if "weights" not in str(exc):
            raise
        return await request.app.state.agent.search_quotes(
            req.query,
            min_price=req.minPrice,
            max_price=req.maxPrice,
            delivery_time=req.deliveryTime,
        )


@router.post("/search-jobs", response_model=ComparisonJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_comparison_job(
    req: ComparisonSearchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ComparisonJobResponse:
    """Create an asynchronous quote-comparison job and return immediately."""
    _prune_jobs()
    job_id = uuid4().hex
    job = _ComparisonJobState(
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
    _append_event(job, "queued", "Queued quote comparison job", 0)
    _COMPARISON_JOBS[job_id] = job
    asyncio.create_task(_run_comparison_job(job_id, req, request.app.state.agent))
    return _public_job(job)


@router.get("/search-jobs/{job_id}", response_model=ComparisonJobResponse)
async def get_comparison_job(
    job_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> ComparisonJobResponse:
    job = _COMPARISON_JOBS.get(job_id)
    if job is None or job.owner != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Comparison job not found"},
        )
    return _public_job(job)


@router.get("/search-jobs/{job_id}/events")
async def stream_comparison_job_events(
    job_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> StreamingResponse:
    job = _COMPARISON_JOBS.get(job_id)
    if job is None or job.owner != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Comparison job not found"},
        )
    return StreamingResponse(
        _stream_comparison_job_events(job_id, current_user.email),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
