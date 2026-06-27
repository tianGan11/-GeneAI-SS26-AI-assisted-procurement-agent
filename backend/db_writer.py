"""
db_writer.py
============
负责把搜索结果"写回"数据库：
  - 记录这次搜索请求 (procurement_request)
  - 把网络搜到的新供应商存进 sourcing_candidate（临时候选区，不污染 supplier）
  - 把搜到的产品存进 product 表（comparison流程，去重，按 name_de）
  - 用户点击 Select & Rate 后，把 candidate "转正"复制进 supplier

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
      2. 遍历 suppliers：
         - 如果已经在 supplier 表里（按 name 匹配）→ 跳过，不动
         - 如果是新发现的（数据库里没有）→ 插入 sourcing_candidate（不是 supplier！）
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

        # 2. 遍历供应商
        for supplier in suppliers:
            name = supplier.get("name")
            if not name:
                continue

            # 查重：name 是否已存在于正式的 supplier 表
            cur.execute("SELECT id FROM supplier WHERE name = %s", (name,))
            existing = cur.fetchone()
            if existing:
                continue  # 已经是正式供应商，跳过

            # 新发现的供应商 → 存进 sourcing_candidate（候选区），不直接进 supplier
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

            # 候选区里也按 name 去重，避免重复搜索同一供应商堆积多条
            cur.execute("SELECT id FROM sourcing_candidate WHERE name = %s", (name,))
            existing_candidate = cur.fetchone()
            if existing_candidate:
                continue

            cur.execute(
                """
                INSERT INTO sourcing_candidate
                    (name, origin, website, country, contact_name,
                     contact_email, contact_phone, scale, rating, attributes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    "web",  # 进候选区的，统一标记为 web 来源
                    supplier.get("website"),
                    supplier.get("country"),
                    supplier.get("contactPerson"),
                    supplier.get("email"),
                    supplier.get("phone"),
                    supplier.get("employees"),
                    (supplier.get("matchScore", 0) or 0) / 20,
                    json.dumps(attributes, ensure_ascii=False),
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[db_writer] 保存 sourcing 结果失败: {e}")
    finally:
        conn.close()


def promote_candidate_to_supplier(candidate_name: str) -> bool:
    """
    用户点击 "Select & Rate" 并完成评分后调用。
    把 sourcing_candidate 里这条记录，复制一份到正式的 supplier 表（origin 保持 web）。

    返回 True 表示成功转正，False 表示没找到这个候选人。
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 先确认 supplier 表里还没有这个名字（避免重复插入）
        cur.execute("SELECT id FROM supplier WHERE name = %s", (candidate_name,))
        if cur.fetchone():
            return True  # 已经是正式供应商了，算成功

        # 从候选区找到这条记录
        cur.execute("SELECT * FROM sourcing_candidate WHERE name = %s", (candidate_name,))
        candidate = cur.fetchone()
        if not candidate:
            return False

        # 复制进 supplier 表
        cur.execute(
            """
            INSERT INTO supplier
                (name, origin, website, country, contact_name,
                 contact_email, contact_phone, scale, rating, attributes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                candidate["name"],
                "web",  # 来源仍然是 web，只是现在"转正"成了正式供应商
                candidate["website"],
                candidate["country"],
                candidate["contact_name"],
                candidate["contact_email"],
                candidate["contact_phone"],
                candidate["scale"],
                candidate["rating"],
                json.dumps(candidate["attributes"]) if candidate["attributes"] else None,
            ),
        )

        # 转正后从候选区删除，避免候选区越堆越多
        cur.execute("DELETE FROM sourcing_candidate WHERE name = %s", (candidate_name,))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[db_writer] 转正供应商失败: {e}")
        return False
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

    注：Comparison 流程暂不引入 candidate 中转，因为报价数据本身就需要
        直接关联 product，业务含义和"寻源候选"不同。
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
                            "web",
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
                continue

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