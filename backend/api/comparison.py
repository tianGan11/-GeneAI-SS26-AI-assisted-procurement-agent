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
from db_writer import save_comparison_request_and_products  # 新加的 import


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
    result = await request.app.state.agent.search_quotes(
        req.query,
        min_price=req.minPrice,
        max_price=req.maxPrice,
        delivery_time=req.deliveryTime,
    )
    # 自动把这次搜索结果存进数据库
    try:
        save_comparison_request_and_products(
            request_text=req.query,
            requested_by=current_user.email,
            items=result.get("results", []),
        )
    except Exception as e:
        print(f"[comparison] 保存数据库失败，不影响返回结果: {e}")
    return result