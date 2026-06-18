"""
database.py
===========
数据库查询逻辑。
你们负责写查询，数据库同学负责建表和填数据。

现在：返回 mock 数据
开会后：换成真实 PostgreSQL 查询
"""

import os
# 数据库同学建好后取消注释：
# import psycopg2
# from psycopg2.extras import RealDictCursor


# ═══════════════════════════════════════════════════════
# 数据库连接
# ═══════════════════════════════════════════════════════

def get_connection():
    """
    获取数据库连接。
    连接信息从 .env 文件读取，不要写死在代码里。

    开会时让数据库同学提供：
        DB_HOST=xxx
        DB_PORT=5432
        DB_NAME=procureai
        DB_USER=xxx
        DB_PASSWORD=xxx
    """
    # TODO: 数据库同学给出连接信息后取消注释
    # return psycopg2.connect(
    #     host=os.getenv("DB_HOST"),
    #     port=os.getenv("DB_PORT", 5432),
    #     dbname=os.getenv("DB_NAME"),
    #     user=os.getenv("DB_USER"),
    #     password=os.getenv("DB_PASSWORD"),
    # )
    pass


# ═══════════════════════════════════════════════════════
# 开会时给数据库同学看的表结构
# ═══════════════════════════════════════════════════════

"""
suppliers 表：
    id              VARCHAR PRIMARY KEY
    name            VARCHAR
    category        VARCHAR
    country         VARCHAR
    city            VARCHAR
    address         VARCHAR
    contact_person  VARCHAR
    phone           VARCHAR
    email           VARCHAR
    website         VARCHAR
    employees       VARCHAR
    annual_revenue  VARCHAR
    established     INT
    capabilities    TEXT[]
    certifications  TEXT[]

products 表：
    id              VARCHAR PRIMARY KEY
    supplier_id     VARCHAR REFERENCES suppliers(id)
    sku             VARCHAR
    name            VARCHAR
    unit_price_eur  FLOAT
    stock           INT
    delivery_days   INT
    delivery_label  VARCHAR
    payment_term    VARCHAR
    payment_label   VARCHAR
    delivery_method VARCHAR
    rating          FLOAT
    reviews         INT
"""


# ═══════════════════════════════════════════════════════
# 查询函数
# ═══════════════════════════════════════════════════════

async def query_suppliers(
    category: str | None = None,
    certifications: list[str] | None = None,
    country: str | None = None,
) -> list[dict]:
    """
    查询供应商表。

    开会后换成真实 SQL：
        SELECT * FROM suppliers
        WHERE category = %s
        AND certifications @> %s
    """

    # ── 现在返回 mock 数据 ────────────────────────────────────────────────
    return [
        {
            "id": "sup-001",
            "name": "Freudenberg Sealing Technologies GmbH",
            "category": "rubberSeal",
            "country": "Germany",
            "city": "Weinheim",
            "address": "Höhnerweg 2-4, 69469 Weinheim, Germany",
            "contactPerson": "Klaus Bauer",
            "phone": "+49 6201 80-0",
            "email": "procurement@freudenberg-et.com",
            "website": "www.freudenberg-et.com",
            "employees": "10,000+",
            "annualRevenue": "€ 2B+",
            "established": 1849,
            "capabilities": ["Rubber Seals", "Gaskets", "Vibration Control", "Custom Molding"],
            "certifications": ["IATF 16949", "ISO 14001", "ISO 9001"],
            "matchScore": 94,
        },
        {
            "id": "sup-002",
            "name": "Sika Automotive GmbH",
            "category": "glassAdhesive",
            "country": "Germany",
            "city": "Hamburg",
            "address": "Reichsbahnstraße 99, 22525 Hamburg, Germany",
            "contactPerson": "Anna Müller",
            "phone": "+49 40 54002-0",
            "email": "automotive@sika.com",
            "website": "www.sika.com/automotive",
            "employees": "5,000–10,000",
            "annualRevenue": "€ 500M–1B",
            "established": 1910,
            "capabilities": ["PVB Lamination", "Urethane Adhesives", "Glass Bonding", "NVH Solutions"],
            "certifications": ["IATF 16949", "ISO 9001", "VDA 6.1"],
            "matchScore": 89,
        },
    ]

    # ── 开会后换成真实查询（把上面 return 注释掉，取消下面注释）─────────────
    # conn = get_connection()
    # cur = conn.cursor(cursor_factory=RealDictCursor)
    # query = "SELECT * FROM suppliers WHERE 1=1"
    # params = []
    # if category:
    #     query += " AND category = %s"
    #     params.append(category)
    # if certifications:
    #     query += " AND certifications @> %s"
    #     params.append(certifications)
    # if country:
    #     query += " AND country = %s"
    #     params.append(country)
    # cur.execute(query, params)
    # return cur.fetchall()


async def query_products(
    sku: str | None = None,
    max_price: float | None = None,
    max_delivery_days: int | None = None,
) -> list[dict]:
    """
    查询产品报价表。

    开会后换成真实 SQL：
        SELECT p.*, s.name as vendor
        FROM products p
        JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.unit_price_eur <= %s
        AND p.delivery_days <= %s
    """

    # ── 现在返回 mock 数据 ────────────────────────────────────────────────
    return [
        {
            "id": "vendor-001",
            "vendor": "Bechtle AG",
            "platform": "Bechtle Online Shop",
            "product": "Cisco ISR 4331 — Enterprise Router (Generalüberholt)",
            "matchScore": 96,
            "unitPriceEur": 2180.0,
            "unitLabel": "€ 2.180 / Stk.",
            "deliveryDays": 4,
            "deliveryLabel": "3–5 Werktage",
            "paymentTerm": "onAccount",
            "paymentLabel": "Invoice (Rechnung 30 Tage)",
            "deliveryMethod": "DHL Express",
            "rating": 4.8,
            "reviews": 124,
        },
        {
            "id": "vendor-002",
            "vendor": "Saturn Business",
            "platform": "MediaMarktSaturn Pro",
            "product": "Ubiquiti UniFi Dream Machine Pro — Gateway & Controller",
            "matchScore": 91,
            "unitPriceEur": 1950.0,
            "unitLabel": "€ 1.950 / unit",
            "deliveryDays": 6,
            "deliveryLabel": "5–7 business days",
            "paymentTerm": "card",
            "paymentLabel": "Credit Card / PayPal",
            "deliveryMethod": "UPS Standard",
            "rating": 4.6,
            "reviews": 89,
        },
        {
            "id": "vendor-003",
            "vendor": "Axesso Systems GmbH",
            "platform": "ITscope B2B Marketplace",
            "product": "HPE Aruba Instant On AP22 (5-Pack) — WiFi Access Point",
            "matchScore": 88,
            "unitPriceEur": 2320.0,
            "unitLabel": "€ 2.320 / Stk.",
            "deliveryDays": 8,
            "deliveryLabel": "7–10 Werktage",
            "paymentTerm": "prepayment",
            "paymentLabel": "Prepayment (Vorkasse)",
            "deliveryMethod": "Freight Forwarding (Spedition)",
            "rating": 4.5,
            "reviews": 56,
        },
    ]

    # ── 开会后换成真实查询（把上面 return 注释掉，取消下面注释）─────────────
    # conn = get_connection()
    # cur = conn.cursor(cursor_factory=RealDictCursor)
    # query = """
    #     SELECT p.*, s.name as vendor
    #     FROM products p
    #     JOIN suppliers s ON p.supplier_id = s.id
    #     WHERE 1=1
    # """
    # params = []
    # if sku:
    #     query += " AND p.sku = %s"
    #     params.append(sku)
    # if max_price:
    #     query += " AND p.unit_price_eur <= %s"
    #     params.append(max_price)
    # if max_delivery_days:
    #     query += " AND p.delivery_days <= %s"
    #     params.append(max_delivery_days)
    # cur.execute(query, params)
    # return cur.fetchall()
