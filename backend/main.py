"""
ProcureAI Backend — FastAPI
严格按照 docs/openapi.yaml 实现所有接口
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import uvicorn
import time
import uuid

from agent_interface import run_sourcing_agent, run_comparison_agent

app = FastAPI(title="Fuyao Procurement Cloud API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


# ═══════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════

def error(code: str, message: str, status: int):
    raise HTTPException(status_code=status, detail={"error": {"code": code, "message": message}})

def now_ms() -> int:
    return int(time.time() * 1000)


# ═══════════════════════════════════════════════════════
# 数据模型（严格对应 openapi.yaml）
# ═══════════════════════════════════════════════════════

# ── Auth ──────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class AuthUser(BaseModel):
    email: str
    name: str
    company: str
    role: str

class LoginResponse(BaseModel):
    token: str
    user: AuthUser

# ── Vault ─────────────────────────────────────────────
class VaultKey(BaseModel):
    id: str
    label: str
    maskedValue: str
    updatedAt: int

class VaultKeyCreate(BaseModel):
    label: str
    secret: str

# ── Sourcing ──────────────────────────────────────────
class SourcingRequest(BaseModel):
    query: str

# ── Comparison ────────────────────────────────────────
class ComparisonSearchRequest(BaseModel):
    query: str
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    deliveryTime: Optional[str] = "unlimited"

# ── Conversations ─────────────────────────────────────
class ConversationRestore(BaseModel):
    query: str
    minPrice: Optional[str] = None
    maxPrice: Optional[str] = None
    deliveryTime: Optional[str] = None
    weights: Optional[dict] = None

class FeedbackRecord(BaseModel):
    chosenName: str
    quality: int
    logistics: int
    priceSatisfaction: int
    service: int
    comment: str
    submittedAt: int

class NewConversation(BaseModel):
    module: str
    query: str
    filters: dict
    restore: Optional[ConversationRestore] = None
    resultCount: int
    candidateNames: list[str]

class ConversationRecord(BaseModel):
    id: str
    timestamp: int
    module: str
    query: str
    filters: dict
    restore: Optional[ConversationRestore] = None
    resultCount: int
    candidateNames: list[str]
    feedback: Optional[FeedbackRecord] = None


# ═══════════════════════════════════════════════════════
# Mock 数据存储（等数据库同学建好表后替换）
# ═══════════════════════════════════════════════════════

# 模拟用户数据库
MOCK_USERS = {
    "user@fuyao.com": {
        "password": "password123",
        "user": AuthUser(
            email="user@fuyao.com",
            name="Demo User",
            company="Fuyao Europe",
            role="Procurement Manager",
        )
    }
}

# 模拟 token 存储
MOCK_TOKENS: dict[str, AuthUser] = {}

# 模拟对话记录存储
MOCK_CONVERSATIONS: dict[str, ConversationRecord] = {}

# 模拟 Vault 存储
MOCK_VAULT: dict[str, VaultKey] = {}


# ═══════════════════════════════════════════════════════
# Auth 辅助
# ═══════════════════════════════════════════════════════

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthUser:
    """验证 JWT token，返回当前用户"""
    # TODO: 换成真实 JWT 验证
    if not credentials:
        error("UNAUTHORIZED", "Missing token", 401)
    token = credentials.credentials
    user = MOCK_TOKENS.get(token)
    if not user:
        error("INVALID_TOKEN", "Token is invalid or expired", 401)
    return user


# ═══════════════════════════════════════════════════════
# Auth 端点
# ═══════════════════════════════════════════════════════

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """登录，返回 JWT 和用户信息"""
    user_data = MOCK_USERS.get(req.email)
    if not user_data or user_data["password"] != req.password:
        error("INVALID_CREDENTIALS", "Email or password is incorrect", 401)
    token = str(uuid.uuid4())
    MOCK_TOKENS[token] = user_data["user"]
    return LoginResponse(token=token, user=user_data["user"])


@app.get("/api/auth/me", response_model=AuthUser)
async def me(current_user: AuthUser = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user


@app.post("/api/auth/logout", status_code=204)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """登出，使 token 失效"""
    if credentials:
        MOCK_TOKENS.pop(credentials.credentials, None)


# ═══════════════════════════════════════════════════════
# Vault 端点
# ═══════════════════════════════════════════════════════

@app.get("/api/vault/keys", response_model=list[VaultKey])
async def list_vault_keys(current_user: AuthUser = Depends(get_current_user)):
    """列出用户存储的 API Key（只返回脱敏值）"""
    return list(MOCK_VAULT.values())


@app.post("/api/vault/keys", response_model=VaultKey, status_code=201)
async def save_vault_key(req: VaultKeyCreate, current_user: AuthUser = Depends(get_current_user)):
    """存储新的 API Key（加密存储，只返回脱敏值）"""
    key = VaultKey(
        id=str(uuid.uuid4()),
        label=req.label,
        maskedValue="••••••••" + req.secret[-4:] if len(req.secret) >= 4 else "••••",
        updatedAt=now_ms(),
    )
    MOCK_VAULT[key.id] = key
    return key


@app.delete("/api/vault/keys/{id}", status_code=204)
async def delete_vault_key(id: str, current_user: AuthUser = Depends(get_current_user)):
    """删除一个 API Key"""
    MOCK_VAULT.pop(id, None)


# ═══════════════════════════════════════════════════════
# Sourcing 端点
# ═══════════════════════════════════════════════════════

@app.post("/api/sourcing/search")
async def sourcing_search(
    req: SourcingRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """供应商寻源"""
    try:
        result = await run_sourcing_agent(query=req.query)
        # 对齐前端期望的格式：{ results: [...] }
        return {"results": result.get("suppliers", [])}
    except Exception as e:
        error("AGENT_ERROR", str(e), 500)


# ═══════════════════════════════════════════════════════
# Comparison 端点
# ═══════════════════════════════════════════════════════

@app.post("/api/comparison/search")
async def comparison_search(
    req: ComparisonSearchRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """报价比对"""
    try:
        result = await run_comparison_agent(
            query=req.query,
            max_price=req.maxPrice,
            delivery_option=req.deliveryTime or "unlimited",
        )
        # 对齐前端期望的格式：{ results: [...] }
        return {"results": result.get("items", [])}
    except Exception as e:
        error("AGENT_ERROR", str(e), 500)


# ═══════════════════════════════════════════════════════
# Conversations 端点
# ═══════════════════════════════════════════════════════

@app.get("/api/conversations", response_model=list[ConversationRecord])
async def list_conversations(current_user: AuthUser = Depends(get_current_user)):
    """获取历史对话记录（最新在前）"""
    records = sorted(MOCK_CONVERSATIONS.values(), key=lambda r: r.timestamp, reverse=True)
    return records


@app.post("/api/conversations", response_model=ConversationRecord, status_code=201)
async def create_conversation(
    req: NewConversation,
    current_user: AuthUser = Depends(get_current_user),
):
    """记录一次查询"""
    record = ConversationRecord(
        id=str(uuid.uuid4()),
        timestamp=now_ms(),
        **req.model_dump(),
    )
    MOCK_CONVERSATIONS[record.id] = record
    return record


@app.delete("/api/conversations", status_code=204)
async def clear_conversations(current_user: AuthUser = Depends(get_current_user)):
    """清空所有对话记录"""
    MOCK_CONVERSATIONS.clear()


@app.patch("/api/conversations/{id}/feedback", response_model=ConversationRecord)
async def attach_feedback(
    id: str,
    feedback: FeedbackRecord,
    current_user: AuthUser = Depends(get_current_user),
):
    """给对话记录附加反馈"""
    record = MOCK_CONVERSATIONS.get(id)
    if not record:
        error("NOT_FOUND", f"Conversation {id} not found", 404)
    record.feedback = feedback
    return record


@app.delete("/api/conversations/{id}", status_code=204)
async def delete_conversation(id: str, current_user: AuthUser = Depends(get_current_user)):
    """删除单条对话记录"""
    MOCK_CONVERSATIONS.pop(id, None)


# ═══════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
