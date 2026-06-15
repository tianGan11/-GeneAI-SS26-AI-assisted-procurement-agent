from __future__ import annotations

import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from api.auth import AuthUser, get_current_user


router = APIRouter(prefix="/api/vault", tags=["vault"])


class VaultKeyCreate(BaseModel):
    label: str = Field(min_length=1)
    secret: str = Field(min_length=1)


class VaultKey(BaseModel):
    id: str
    label: str
    maskedValue: str
    updatedAt: int


class VaultRecord(VaultKey):
    secret: str


MOCK_VAULT: dict[str, dict[str, VaultRecord]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _mask_secret(secret: str) -> str:
    suffix = secret[-4:] if len(secret) >= 4 else secret
    return f"{'*' * 8}{suffix}"


@router.get("/keys", response_model=list[VaultKey])
async def list_keys(current_user: Annotated[AuthUser, Depends(get_current_user)]) -> list[VaultKey]:
    records = MOCK_VAULT.get(current_user.email, {})
    return [VaultKey(**record.model_dump(exclude={"secret"})) for record in records.values()]


@router.post("/keys", response_model=VaultKey, status_code=status.HTTP_201_CREATED)
async def save_key(
    req: VaultKeyCreate,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> VaultKey:
    records = MOCK_VAULT.setdefault(current_user.email, {})
    key_id = uuid4().hex
    record = VaultRecord(
        id=key_id,
        label=req.label,
        maskedValue=_mask_secret(req.secret),
        updatedAt=_now_ms(),
        secret=req.secret,
    )
    records[key_id] = record
    return VaultKey(**record.model_dump(exclude={"secret"}))


@router.delete("/keys/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    id: str,
    response: Response,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    MOCK_VAULT.get(current_user.email, {}).pop(id, None)
    response.status_code = status.HTTP_204_NO_CONTENT
