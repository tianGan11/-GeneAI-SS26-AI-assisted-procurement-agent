from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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

# ---------------------------------------------------------------------------
# FastAPI standard security scheme — fixes Swagger UI "Authorize" button
# Previously used Header(alias="Authorization") which OpenAPI treated as a
# plain header param, so the generated spec had no securitySchemes and
# Swagger never sent the token. HTTPBearer registers a proper bearer
# security scheme that the Authorize button binds to automatically.
# ---------------------------------------------------------------------------

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)] = None,
) -> AuthUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    email = MOCK_TOKENS.get(token)
    record = MOCK_USERS.get(email or "")
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
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
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    # get_current_user already validated the token and returns the user
    # — just signal success (the frontend drops the token client-side).
    response.status_code = status.HTTP_204_NO_CONTENT
