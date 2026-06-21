"""
Sourcing API — supplier discovery.

Optimization over the original:
  - Added auth protection via Depends(get_current_user) so the endpoint
    requires a valid Bearer token, matching the openapi.yaml contract.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/sourcing", tags=["sourcing"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


@router.post("/search")
async def search(
    req: SearchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """
    POST /api/sourcing/search — match openapi.yaml spec.

    Protected: requires Authorization: Bearer <token> header.
    """
    return await request.app.state.agent.search_suppliers(req.query)
