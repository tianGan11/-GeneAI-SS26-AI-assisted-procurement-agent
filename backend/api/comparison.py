"""
Comparison API — standard-product quote benchmarking.

Optimization over the original:
  - Added auth protection via Depends(get_current_user) so the endpoint
    requires a valid Bearer token, matching the openapi.yaml contract.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/comparison", tags=["comparison"])


class ComparisonSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    deliveryTime: Optional[str] = None


@router.post("/search")
async def search(
    req: ComparisonSearchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """
    POST /api/comparison/search — match openapi.yaml spec.

    Protected: requires Authorization: Bearer <token> header.
    """
    return await request.app.state.agent.search_quotes(
        req.query,
        min_price=req.minPrice,
        max_price=req.maxPrice,
        delivery_time=req.deliveryTime,
    )
