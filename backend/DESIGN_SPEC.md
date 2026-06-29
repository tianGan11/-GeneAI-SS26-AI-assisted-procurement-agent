# ProcureAI Backend — Design Spec

## Architecture

```
用户输入 → FastAPI → Agent Core → 返回结构化结果
                       ├→ 向量检索 (ChromaDB)
                       ├→ LLM 打分排序
                       └→ 网络搜索 (fallback)
```

## Tech Stack
- Python 3.11+ / FastAPI / Pydantic v2
- LangChain (agent orchestration)
- ChromaDB (local vector store)
- sentence-transformers (local embedding, model: BAAI/bge-m3)
- OpenAI-compatible API for LLM (model via LLM_MODEL env)
- duckduckgo-search (web fallback)

## Files to Create

### 1. `data/suppliers.json`
Migrate exactly 7 suppliers from the frontend mock data (src/data/suppliers.ts). 
Each supplier JSON object:
```json
{
  "id": "sup-1",
  "name": "Henkel AG & Co. KGaA",
  "category": "glassAdhesive",
  "country": "Germany",
  "city": "Düsseldorf",
  "description": "Global leader in adhesives, automotive polyurethane windscreen adhesives (Teroson), primerless direct-glazing systems, OEM-approved cure profiles",
  "products": ["Teroson PU 8597 HMLC", "Teroson PU 9225", "Primer 207 Glass Activator"],
  "certifications": ["IATF 16949", "ISO 9001", "ISO 14001"],
  "contactPerson": "Markus Bauer",
  "phone": "+49 211 797 0",
  "email": "automotive@henkel.com",
  "website": "www.henkel-adhesives.com",
  "employees": "50000+",
  "annualRevenue": "€ 22B+",
  "established": 1876,
  "capabilities": ["Polyurethane windscreen adhesives", "Primerless direct-glazing", "High-modulus structural bonding", "OEM-approved cure profiles"],
  "matchScore": 97
}
```
All 7 suppliers: Henkel(sup-1), Sika Automotive(sup-2), CQLT SaarGummi(sup-3), Cooper Standard France(sup-4), Şişecam Automotive(sup-5), Wilhelm Böllhoff(sup-6), DS Smith Packaging(sup-7).

### 2. `data/quotes.json`
Migrate exactly 5 quotes from the frontend mock data (src/data/comparison.ts):
```json
{
  "id": "cmp-1",
  "vendor": "Henkel Direct",
  "platform": "Henkel B2B Portal",
  "product": "Teroson PU 8597 HMLC — Windscreen Adhesive (310 ml, Karton 12 Stk.)",
  "matchScore": 96,
  "unitPriceEur": 11.4,
  "unitLabel": "€ 11,40 / Kartusche",
  "deliveryDays": 4,
  "deliveryLabel": "3–5 Werktage",
  "paymentTerm": "onAccount",
  "paymentLabel": "Invoice (Rechnung 30 Tage)",
  "deliveryMethod": "DHL Express",
  "rating": 4.8,
  "reviews": 124,
  "category": "glassAdhesive"
}
```

### 3. `agent/parser.py` — IntentParser
Parse natural language procurement query into structured intent:
```python
from pydantic import BaseModel
from typing import Optional

class ProcurementIntent(BaseModel):
    category: Optional[str] = None  # glassAdhesive, rubberSeal, waterDeflector, glassRaw, hardware, packaging
    country: Optional[str] = None
    certifications: list[str] = []
    max_price: Optional[float] = None
    max_delivery_days: Optional[int] = None
    keywords: list[str] = []  # extracted key terms for search

class IntentParser:
    def __init__(self, llm): ...
    async def parse(self, query: str) -> ProcurementIntent: ...
```

Uses LLM with structured output (Pydantic model) to extract intent. The prompt instructs the LLM to identify category, country, certifications, price constraints, delivery constraints, and keywords from natural language text in Chinese/English/German.

### 4. `agent/retriever.py` — SupplierRetriever
```python
class SupplierRetriever:
    def __init__(self, chroma_collection, suppliers: list[dict]): ...
    
    async def search(self, intent: ProcurementIntent, top_k: int = 10) -> list[dict]:
        """Search local vector DB by intent. If results < 3 or top score < 60, fallback to web search."""
        ...
    
    async def _web_search(self, intent: ProcurementIntent) -> list[dict]:
        """Use duckduckgo to find suppliers, then LLM to extract structured info."""
        ...
```

Build ChromaDB collection from suppliers.json on init. Search by combining intent fields into a query string. Use sentence-transformers locally for embedding (no API call needed).

### 5. `agent/ranker.py` — LLMRanker
```python
class LLMRanker:
    def __init__(self, llm): ...
    
    async def rank_suppliers(self, query: str, candidates: list[dict]) -> list[dict]:
        """Score each candidate 0-100 based on query relevance. Return sorted by matchScore with reasons."""
        ...
    
    async def rank_quotes(self, query: str, candidates: list[dict], 
                          min_price: float = None, max_price: float = None,
                          max_delivery_days: int = None) -> list[dict]:
        """Score quotes, apply hard filters, return sorted."""
        ...
```

Uses LLM with structured output to score each candidate. For quotes, applies hard filters (price range, delivery days) before scoring.

### 6. `agent/procurement_agent.py` — Main Orchestrator
```python
class ProcurementAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"))
        self.parser = IntentParser(self.llm)
        self.retriever = SupplierRetriever(chroma_collection, suppliers)
        self.ranker = LLMRanker(self.llm)
    
    async def search_suppliers(self, query: str) -> dict:
        """Full pipeline: parse → retrieve → rank → return"""
        intent = await self.parser.parse(query)
        candidates = await self.retriever.search(intent)
        ranked = await self.ranker.rank_suppliers(query, candidates)
        return {"results": ranked}
    
    async def search_quotes(self, query: str, min_price=None, max_price=None, 
                            delivery_time=None) -> dict:
        """Full pipeline for quote comparison"""
        ...
```

### 7. `api/sourcing.py` — Sourcing API Routes
```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/sourcing", tags=["sourcing"])

class SearchRequest(BaseModel):
    query: str

@router.post("/search")
async def search(req: SearchRequest):
    """POST /api/sourcing/search — match openapi.yaml spec"""
    ...
```

### 8. `api/comparison.py` — Comparison API Routes
```python
class ComparisonSearchRequest(BaseModel):
    query: str
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    deliveryTime: Optional[str] = None  # "unlimited" | "within3" | "within7"

@router.post("/search")
async def search(req: ComparisonSearchRequest):
    """POST /api/comparison/search — match openapi.yaml spec"""
    ...
```

### 9. `main.py` — FastAPI App Entry
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load data, build vector index, init agent
    app.state.agent = ProcurementAgent()
    yield
    # Shutdown: cleanup

app = FastAPI(title="ProcureAI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

from api.sourcing import router as sourcing_router
from api.comparison import router as comparison_router
app.include_router(sourcing_router)
app.include_router(comparison_router)

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

### 10. `trainer/dspy_optimizer.py` — DSPy Training Pipeline (placeholder, full later)
```python
class DSPyTrainer:
    def __init__(self, agent: ProcurementAgent): ...
    def add_feedback(self, query: str, recommended_supplier: str, feedback: dict): ...
    async def optimize(self) -> dict: ...
```

## Key Design Decisions

1. **Local embedding (sentence-transformers + BGE-M3)**: Free, offline, no API cost for retrieval
2. **LLM only for parsing + ranking**: Cost-efficient — embedding is local, LLM used only twice per query
3. **ChromaDB persistent**: Survives restarts, data in ./chroma_data/
4. **Web search as fallback**: Only triggered when local results insufficient
5. **FastAPI lifespan**: Agent initialized once at startup, reused across requests
6. **CORS wide open for dev**: Frontend on localhost:5173 can call without issues

## Verification
- `python main.py` starts without error
- `curl -X POST http://localhost:8000/api/sourcing/search -H "Content-Type: application/json" -d '{"query":"find glass adhesive suppliers in Germany"}'` returns valid JSON with results
- `curl http://localhost:8000/api/health` returns {"status": "ok"}
