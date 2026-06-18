from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/comparison", tags=["comparison"])


class ComparisonSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    deliveryTime: Optional[str] = None


@router.post("/search")
async def search(req: ComparisonSearchRequest, request: Request):
    """POST /api/comparison/search — match openapi.yaml spec"""
    return await request.app.state.agent.search_quotes(
        req.query,
        min_price=req.minPrice,
        max_price=req.maxPrice,
        delivery_time=req.deliveryTime,
    )
