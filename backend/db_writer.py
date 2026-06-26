"""
db_writer.py
============
负责把搜索结果"写回"数据库：
  - 记录这次搜索请求 (procurement_request)
  - 把搜到的供应商存进 supplier 表（去重，按 name）
  - 把搜到的产品存进 product 表（去重，按 name_de）

调用时机：每次 /api/sourcing/search 或 /api/comparison/search
         拿到结果后自动调用，不需要用户手动保存。
"""

from database import get_connection
from psycopg2.extras import RealDictCursor
import json


def save_sourcing_request_and_suppliers(
    request_text: str,
    requested_by: str,
    suppliers: list[dict],
) -> None:
    """
    保存一次 Sourcing 搜索：
      1. 插入 procurement_request
      2. 遍历 suppliers，按 name 去重后插入 supplier 表
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. 插入这次请求记录
        cur.execute(
            """
            INSERT INTO procurement_request (request_text, requested_by, status)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (request_text, requested_by, "closed"),
        )
        conn.commit()

        # 2. 遍历供应商，按 name 去重后插入
        for supplier in suppliers:
            name = supplier.get("name")
            if not name:
                continue

            # 新发现的供应商统一标记为 web
            # 只有用户点击 "Select & Rate" 评分后才会变成 internal（另一个函数处理）
            origin = "web"

            # 查重：name 是否已存在
            cur.execute("SELECT id FROM supplier WHERE name = %s", (name,))
            existing = cur.fetchone()
            if existing:
                continue  # 已存在，跳过

            attributes = {
                "category": supplier.get("category"),
                "city": supplier.get("city"),
                "address": supplier.get("address"),
                "description": supplier.get("description"),
                "products": supplier.get("products", []),
                "capabilities": supplier.get("capabilities", []),
                "certifications": supplier.get("certifications", []),
                "annualRevenue": supplier.get("annualRevenue"),
                "established": supplier.get("established"),
            }

            cur.execute(
                """
                INSERT INTO supplier
                    (name, origin, website, country, contact_name,
                     contact_email, contact_phone, scale, rating, attributes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    origin,
                    supplier.get("website"),
                    supplier.get("country"),
                    supplier.get("contactPerson"),
                    supplier.get("email"),
                    supplier.get("phone"),
                    supplier.get("employees"),
                    (supplier.get("matchScore", 0) or 0) / 20,  # matchScore(0-100) 转成 rating(0-5)
                    json.dumps(attributes, ensure_ascii=False),
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[db_writer] 保存 sourcing 结果失败: {e}")
    finally:
        conn.close()


def save_comparison_request_and_products(
    request_text: str,
    requested_by: str,
    items: list[dict],
) -> None:
    """
    保存一次 Comparison 搜索：
      1. 插入 procurement_request
      2. 遍历 items，按 product name 去重后插入 product 表
      3. 同时确保对应的 supplier 也存在（按 vendor name 去重）
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            INSERT INTO procurement_request (request_text, requested_by, status)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (request_text, requested_by, "closed"),
        )
        conn.commit()

        for item in items:
            product_name = item.get("product")
            vendor_name = item.get("vendor")
            # 新发现的供应商统一标记为 web，评分后才转 internal
            origin = "web"

            # ---- 确保 supplier 存在 ----
            supplier_id = None
            if vendor_name:
                cur.execute("SELECT id FROM supplier WHERE name = %s", (vendor_name,))
                existing_supplier = cur.fetchone()
                if existing_supplier:
                    supplier_id = existing_supplier["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO supplier (name, origin, rating, attributes)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            vendor_name,
                            origin,
                            (item.get("rating", 0) or 0),
                            json.dumps({"platform": item.get("platform")}, ensure_ascii=False),
                        ),
                    )
                    supplier_id = cur.fetchone()["id"]
                    conn.commit()

            # ---- 确保 product 存在 ----
            if not product_name:
                continue
            cur.execute("SELECT id FROM product WHERE name_de = %s", (product_name,))
            existing_product = cur.fetchone()
            if existing_product:
                continue  # 已存在，跳过

            attributes = {
                "platform": item.get("platform"),
                "paymentTerm": item.get("paymentTerm"),
                "paymentLabel": item.get("paymentLabel"),
                "deliveryMethod": item.get("deliveryMethod"),
                "reviews": item.get("reviews"),
            }

            cur.execute(
                """
                INSERT INTO product
                    (name_de, kind, reference_price, currency, preferred_supplier, attributes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    product_name,
                    "standard",
                    item.get("unitPriceEur"),
                    "EUR",
                    supplier_id,
                    json.dumps(attributes, ensure_ascii=False),
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[db_writer] 保存 comparison 结果失败: {e}")
    finally:
        conn.close()