"""
database.py
===========
数据库查询逻辑，连接 Supabase (PostgreSQL)。
按真实表结构编写：supplier / product / quote / sourcing_candidate
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """获取 Supabase 数据库连接"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 没有设置，检查 .env 文件")
    return psycopg2.connect(database_url)


# ═══════════════════════════════════════════════════════
# Sourcing：查询供应商
# ═══════════════════════════════════════════════════════

async def query_suppliers(
    category: str | None = None,
    country: str | None = None,
) -> list[dict]:
    """
    查询供应商表，返回符合前端 Supplier 格式的数据。

    注意：真实表里没有前端需要的所有字段（比如 capabilities,
    certifications, established, employees, annualRevenue），
    这些字段如果不存在，先用默认值占位，等数据补全。
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                s.id,
                s.name,
                s.country,
                s.website,
                s.contact_name,
                s.contact_email,
                s.contact_phone,
                s.scale,
                s.rating,
                s.attributes
            FROM supplier s
            WHERE 1=1
        """
        params = []
        if country:
            query += " AND s.country = %s"
            params.append(country)
        cur.execute(query, params)
        rows = cur.fetchall()

        # 转换成前端期望的字段名
        results = []
        for row in rows:
            attrs = row.get("attributes") or {}
            results.append({
                "id": str(row["id"]),
                "name": row["name"],
                "category": category or attrs.get("category", "unknown"),
                "country": row["country"] or "",
                "city": attrs.get("city", ""),
                "description": attrs.get("description", ""),
                "products": attrs.get("products", []),
                "address": attrs.get("address", ""),
                "contactPerson": row["contact_name"] or "",
                "phone": row["contact_phone"] or "",
                "email": row["contact_email"] or "",
                "website": row["website"] or "",
                "employees": row["scale"] or "",
                "annualRevenue": attrs.get("annualRevenue", ""),
                "established": attrs.get("established", 0),
                "capabilities": attrs.get("capabilities", []),
                "certifications": attrs.get("certifications", []),
                "matchScore": int(float(row["rating"]) * 20) if row["rating"] else 70,
            })
        return results
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════
# Comparison：查询报价
# ═══════════════════════════════════════════════════════

async def query_products(
    max_price: float | None = None,
    max_delivery_days: int | None = None,
) -> list[dict]:
    """
    查询报价表（quote 联 product 和 supplier），
    返回符合前端 ComparisonItem 格式的数据。
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                q.id,
                q.listing_title,
                q.price,
                q.lead_time_text,
                q.lead_time_days,
                q.score,
                q.attributes AS quote_attrs,
                s.name AS vendor_name,
                p.name_de AS product_name
            FROM quote q
            LEFT JOIN supplier s ON q.supplier_id = s.id
            LEFT JOIN product p ON q.product_id = p.id
            WHERE 1=1
        """
        params = []
        if max_price:
            query += " AND q.price <= %s"
            params.append(max_price)
        if max_delivery_days:
            query += " AND q.lead_time_days <= %s"
            params.append(max_delivery_days)
        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for row in rows:
            attrs = row.get("quote_attrs") or {}
            results.append({
                "id": str(row["id"]),
                "vendor": row["vendor_name"] or "Unknown",
                "platform": attrs.get("platform", ""),
                "product": row["product_name"] or row["listing_title"] or "",
                "matchScore": int(float(row["score"]) * 20) if row["score"] else 70,
                "unitPriceEur": float(row["price"]) if row["price"] else 0.0,
                "unitLabel": f"€ {row['price']}" if row["price"] else "",
                "deliveryDays": row["lead_time_days"] or 0,
                "deliveryLabel": row["lead_time_text"] or "",
                "paymentTerm": attrs.get("paymentTerm", "onAccount"),
                "paymentLabel": attrs.get("paymentLabel", ""),
                "deliveryMethod": attrs.get("deliveryMethod", ""),
                "rating": float(row["score"]) if row["score"] else 0.0,
                "reviews": attrs.get("reviews", 0),
            })
        return results
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════
# 同步版本（给 ProcurementAgent.__init__ 用，因为 __init__ 不能 await）
# ═══════════════════════════════════════════════════════

def query_suppliers_sync() -> list[dict]:
    """
    同步版查询所有供应商，给 Agent 启动时一次性加载用。
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM supplier")
        rows = cur.fetchall()

        results = []
        for row in rows:
            attrs = row.get("attributes") or {}
            results.append({
                "id": str(row["id"]),
                "name": row["name"],
                "category": attrs.get("category", "unknown"),
                "country": row["country"] or "",
                "city": attrs.get("city", ""),
                "description": attrs.get("description", ""),
                "products": attrs.get("products", []),
                "address": attrs.get("address", ""),
                "contactPerson": row["contact_name"] or "",
                "phone": row["contact_phone"] or "",
                "email": row["contact_email"] or "",
                "website": row["website"] or "",
                "employees": row["scale"] or "",
                "annualRevenue": attrs.get("annualRevenue", ""),
                "established": attrs.get("established", 0),
                "capabilities": attrs.get("capabilities", []),
                "certifications": attrs.get("certifications", []),
                "matchScore": int(float(row["rating"]) * 20) if row["rating"] else 70,
            })
        return results
    finally:
        conn.close()

'''comparision模块做完后需要修改本部分代码，目前接到了supplier的数据集上测试是否跑通'''
def query_products_sync() -> list[dict]:
    """
    同步版查询所有报价，给 Agent 启动时一次性加载用。
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                q.id,
                q.listing_title,
                q.price,
                q.lead_time_text,
                q.lead_time_days,
                q.score,
                q.attributes AS quote_attrs,
                s.name AS vendor_name,
                p.name_de AS product_name
            FROM quote q
            LEFT JOIN supplier s ON q.supplier_id = s.id
            LEFT JOIN product p ON q.product_id = p.id
        """)
        rows = cur.fetchall()

        results = []
        for row in rows:
            attrs = row.get("quote_attrs") or {}
            results.append({
                "id": str(row["id"]),
                "vendor": row["vendor_name"] or "Unknown",
                "platform": attrs.get("platform", ""),
                "product": row["product_name"] or row["listing_title"] or "",
                "matchScore": int(float(row["score"]) * 20) if row["score"] else 70,
                "unitPriceEur": float(row["price"]) if row["price"] else 0.0,
                "unitLabel": f"€ {row['price']}" if row["price"] else "",
                "deliveryDays": row["lead_time_days"] or 0,
                "deliveryLabel": row["lead_time_text"] or "",
                "paymentTerm": attrs.get("paymentTerm", "onAccount"),
                "paymentLabel": attrs.get("paymentLabel", ""),
                "deliveryMethod": attrs.get("deliveryMethod", ""),
                "rating": float(row["score"]) if row["score"] else 0.0,
                "reviews": attrs.get("reviews", 0),
                "category": attrs.get("category", ""),
            })
        return results
    finally:
        conn.close()