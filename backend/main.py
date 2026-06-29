"""
ProcureAI Backend — FastAPI application entry point.

Optimizations over the original:
  1. Global exception handler → returns {"error": {"code", "message"}}
     matching the frontend contract (openapi.yaml).
  2. CORS origins configurable via environment variables for deployment.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from agent.procurement_agent import ProcurementAgent
from api.auth import router as auth_router
from api.comparison import router as comparison_router
from api.conversations import router as conversations_router
from api.sourcing import router as sourcing_router
from api.vault import router as vault_router


load_dotenv(override=True)


# ---------------------------------------------------------------------------
# Lifespan — create the shared agent once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = ProcurementAgent()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="ProcureAI API", version="0.1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Register OpenAPI security scheme so Swagger UI shows the "Authorize" button
# for Bearer token auth on every protected endpoint.
# ---------------------------------------------------------------------------

def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["Bearer"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    schema.setdefault("security", []).append({"Bearer": []})
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# CORS — allow frontend dev & production origins
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        *(os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []),
    ],
    allow_origin_regex=os.getenv(
        "CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler — match openapi.yaml error envelope
#   Frontend expects:  { "error": { "code": "…", "message": "…" } }
#   FastAPI default:   { "detail": … }
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(
    request: object, exc: HTTPException
) -> JSONResponse:
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "ERROR", "message": str(exc.detail)}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": detail},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(vault_router)
app.include_router(conversations_router)
app.include_router(sourcing_router)
app.include_router(comparison_router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
