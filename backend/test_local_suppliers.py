"""
一键测试脚本 — 验证供应商寻源模块是否能正确调取本地数据库数据

用法：
  1. 确保计算机网络能连 Supabase
  2. cd backend
  3. python test_local_suppliers.py

会展示：
  - 从 Supabase 读取了多少家供应商
  - 每个测试搜索的匹配结果及分数
  - 是否会触发网络搜索（≥60分=不触发，直接返回本地数据）
"""

import os, sys, re, math, json
from collections import Counter
import psycopg2
from psycopg2.extras import RealDictCursor

if any("pytest" in arg for arg in sys.argv):
    import pytest
    pytest.skip("local database smoke script; requires DATABASE_URL and is not part of automated tests", allow_module_level=True)

# ============================================================
# 配置
# ============================================================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required. Set it in your environment or backend/.env; never hard-code database credentials.")

# ============================================================
# 完全复刻 backend 代码逻辑 (database.py + retriever.py)
# ============================================================

def tokenize(text):
    """复制 retriever.py 的 _tokenize"""
    return re.findall(r"[\w一-鿿äöüÄÖÜß+-]+", text.lower())

def supplier_to_document(supplier):
    """复制 retriever.py 的 _supplier_to_document"""
    fields = [
        supplier.get("name"),
        supplier.get("category"),
        supplier.get("country"),
        supplier.get("city"),
        supplier.get("description"),
        " ".join(supplier.get("products", [])),
        " ".join(supplier.get("certifications", [])),
        " ".join(supplier.get("capabilities", [])),
    ]
    return " ".join(str(f) for f in fields if f)

def lexical_score(query, supplier):
    """复制 retriever.py 的 _lexical_score"""
    query_terms = Counter(tokenize(query))
    supplier_terms = Counter(tokenize(supplier_to_document(supplier)))
    if not query_terms or not supplier_terms:
        return int(supplier.get("matchScore", 0))
    overlap = sum(min(c, supplier_terms[t]) for t, c in query_terms.items())
    norm = math.sqrt(sum(query_terms.values())) * math.sqrt(sum(supplier_terms.values()))
    return round(overlap / norm * 100) if norm else 0

def apply_intent_boosts(supplier, intent_category, intent_country, intent_certs, base_score):
    """复制 retriever.py 的 _apply_intent_boosts"""
    score = int(base_score)
    quality_prior = int(supplier.get("matchScore", 70))

    # 品类匹配 +20/-15
    if intent_category and supplier.get("category") == intent_category:
        score += 20
    elif intent_category:
        score -= 15

    # 地区匹配 +12
    if intent_country and intent_country != "Europe" and supplier.get("country") == intent_country:
        score += 12

    # 认证匹配 +10/-8
    if intent_certs:
        supplier_certs = {c.upper() for c in supplier.get("certifications", [])}
        if all(c.upper() in supplier_certs for c in intent_certs):
            score += 10
        else:
            score -= 8

    # 与 quality_prior(基础质量评分) 加权混合
    score = round(score * 0.75 + quality_prior * 0.25)
    return max(0, min(100, score))

def intent_to_query(category, country, certs=None, keywords=None):
    """复制 retriever.py 的 _intent_to_query"""
    parts = [category or "", country or ""]
    if certs: parts.append(" ".join(certs))
    if keywords: parts.append(" ".join(keywords))
    return " ".join(p for p in parts if p).strip() or "automotive procurement supplier"


# ============================================================
# 从 Supabase 读取供应商（复制 database.py 的 query_suppliers_sync）
# ============================================================

print("=" * 70)
print("  🔍 ProcureAI — 供应商寻源本地数据库测试")
print("=" * 70)
print(f"\n📡 连接 Supabase...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT count(*) FROM supplier")
    total = cur.fetchone()["count"]
    print(f"✅ 连接成功！supplier 表共 {total} 条记录")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    exit(1)

# 加载所有供应商
cur.execute("SELECT * FROM supplier")
rows = cur.fetchall()

suppliers = []
no_attrs = 0
for row in rows:
    attrs = row.get("attributes") or {}
    if attrs == {} or not attrs.get("category"):
        no_attrs += 1
    suppliers.append({
        "id": str(row["id"]),
        "name": row["name"],
        "category": attrs.get("category", "unknown"),
        "country": row["country"] or "",
        "city": attrs.get("city", ""),
        "description": attrs.get("description", ""),
        "products": attrs.get("products", []),
        "certifications": attrs.get("certifications", []),
        "capabilities": attrs.get("capabilities", []),
        "matchScore": int(float(row["rating"]) * 20) if row.get("rating") else 70,
    })

print(f"📦 加载了 {len(suppliers)} 家供应商")
print(f"⚠️  其中 {no_attrs} 条缺少 attributes（旧的空数据）")
print()

# ============================================================
# 测试场景
# ============================================================

test_cases = [
    # (标签, category, country, certs, keywords)
    ("🧪 玻璃胶 · 德国",        "glassAdhesive", "Germany",  [], []),
    ("🧪 挡水条 · 法国",        "waterDeflector", "France", [], []),
    ("🧪 密封条 · 德国",        "rubberSeal",    "Germany",  [], []),
    ("🧪 玻璃原片 · 意大利",    "glassRaw",      "Italy",    [], []),
    ("🧪 五金件 · 德国",        "hardware",      "Germany",  [], []),
    ("🧪 包装 · 德国",          "packaging",     "Germany",  [], []),
    ("🧪 清洁用品 · 德国",      "cleaning",      "Germany",  [], []),
    ("🧪 办公用品 · 德国",      "office",        "Germany",  [], []),
    ("🧪 安全鞋 · 德国",        "safetyShoes",   "Germany",  [], []),
    ("🧪 急救用品 · 德国",      "firstAid",      "Germany",  [], []),
    ("🧪 设备配件 · 德国",      "equipment",     "Germany",  [], []),
    ("🧪 全部品类 · 不限地区",  None,            None,       [], []),
]

all_pass = True

for label, cat, country, certs, keywords in test_cases:
    # 1. 构造查询（同 _intent_to_query）
    query = intent_to_query(cat, country, certs, keywords)

    # 2. 词法评分 + 品类/地区/认证加权（同 _search_local）
    scored = []
    for s in suppliers:
        base = lexical_score(query, s)
        final = apply_intent_boosts(s, cat, country, certs, base)
        scored.append((final, s["name"], s["category"], s.get("country", ""), s.get("source", "database")))

    scored.sort(key=lambda x: x[0], reverse=True)

    top_score = scored[0][0] if scored else 0
    top_name = scored[0][1] if scored else "N/A"
    top_cat = scored[0][2] if scored else ""
    exceeds = top_score >= 60

    if not exceeds:
        all_pass = False

    # 3. 展示
    print(f"\n{'─' * 65}")
    print(f"  {label}")
    print(f"  ── 意图查询: \"{query}\"")

    if cat:
        print(f"  ── 品类: {cat}  地区: {country or '不限'}  认证: {'/'.join(certs) or '无'}")

    flag = "✅ 本地数据直接返回（≥60分，不走网络搜索）" if exceeds else \
           "⚠️  低于60分，会触发网络搜索兜底"
    print(f"  ── 结果: 【{top_score}分】{top_name} ({top_cat}) {flag}")

    # 展示 Top 3
    print(f"  ── Top 3:")
    for i, (sc, nm, cg, co, src) in enumerate(scored[:3], 1):
        star = "⭐" if sc >= 60 else "  "
        print(f"     {star} {sc:>3}分 | {nm:<45} | {cg:<15} | {co}")

    # 展示按品类的前几名
    if cat:
        same_cat = [(sc, nm, cg, co) for sc, nm, cg, co, _ in scored[:10] if cg == cat]
        if same_cat:
            print(f"  ── 同品类({cat})可匹配: {len(same_cat)} 家")

print(f"\n{'=' * 70}")
if all_pass:
    print("  ✅ 全部测试通过！所有品类搜索都能从本地数据库匹配到高分供应商。")
    print("  🎯 直接重启后端即可生效，无需做任何代码修改。")
else:
    print("  ⚠️  部分场景未达60分（如「全部品类不限地区」），这些场景会触发网络搜索补充。")
    print("  💡 这是正常行为——模糊搜索没有足够匹配条件时，网络兜底是合理的。")

print(f"\n📊 数据库供应商品类分布:")
cat_count = Counter(s["category"] for s in suppliers if s["category"] != "unknown")
for c, n in sorted(cat_count.items()):
    names = [s["name"] for s in suppliers if s["category"] == c]
    print(f"  {c:<20} {n}家  →  {', '.join(names[:3])}")
    if len(names) > 3:
        print(f"  {'':>23}还有 {len(names)-3} 家...")

cur.close()
conn.close()
