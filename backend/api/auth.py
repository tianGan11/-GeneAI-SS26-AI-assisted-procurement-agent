from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel


router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthUser(BaseModel):
    email: str
    name: str
    company: str
    role: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: AuthUser


MOCK_USERS: dict[str, dict[str, object]] = {
    "user@fuyao.com": {
        "password": "password123",
        "user": AuthUser(
            email="user@fuyao.com",
            name="Fuyao Procurement User",
            company="Fuyao Glass",
            role="Procurement Manager",
        ),
    }
}
MOCK_TOKENS: dict[str, str] = {}


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing bearer token"},
        )
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthUser:
    token = _extract_bearer_token(authorization)
    email = MOCK_TOKENS.get(token)
    record = MOCK_USERS.get(email or "")
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired token"},
        )
    return record["user"]  # type: ignore[return-value]


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    record = MOCK_USERS.get(req.email)
    if record is None or record["password"] != req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect"},
        )

    token = f"mock-{uuid4().hex}"
    MOCK_TOKENS[token] = req.email
    return LoginResponse(token=token, user=record["user"])  # type: ignore[arg-type]


@router.get("/me", response_model=AuthUser)
async def me(current_user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    token = _extract_bearer_token(authorization)
    MOCK_TOKENS.pop(token, None)
    response.status_code = status.HTTP_204_NO_CONTENT
