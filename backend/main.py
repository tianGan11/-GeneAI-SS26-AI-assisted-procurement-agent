from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.procurement_agent import ProcurementAgent
from api.auth import router as auth_router
from api.comparison import router as comparison_router
from api.conversations import router as conversations_router
from api.sourcing import router as sourcing_router
from api.vault import router as vault_router


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = ProcurementAgent()
    yield


app = FastAPI(title="ProcureAI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(vault_router)
app.include_router(conversations_router)
app.include_router(sourcing_router)
app.include_router(comparison_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
