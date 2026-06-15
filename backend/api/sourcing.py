from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/sourcing", tags=["sourcing"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


@router.post("/search")
async def search(req: SearchRequest, request: Request):
    """POST /api/sourcing/search — match openapi.yaml spec"""
    return await request.app.state.agent.search_suppliers(req.query)
