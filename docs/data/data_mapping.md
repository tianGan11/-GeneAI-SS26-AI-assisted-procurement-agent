# 数据映射说明 · Data Mapping

> 各来源的字段 → 数据库列的对应关系。与 `db_import.py` 里的映射逻辑一致。
> 公共字段进真实列;每类特有的零碎字段进 `attributes`(JSONB)。

---

## 1. 后端 `suppliers.json` → `supplier`

| 来源字段 | 数据库列 | 说明 |
|----------|----------|------|
| `id` | `external_id` | upsert 钥匙(如 `sup-1`) |
| `name` | `name` | |
| —(固定) | `origin = 'web'` | 来自后端寻源 |
| `website` | `website` | |
| `country` | `country` | |
| `contactPerson` | `contact_name` | |
| `email` | `contact_email` | |
| `phone` | `contact_phone` | |
| `employees` | `scale` | 规模 |
| `category`,`city`,`description`,`products`,`certifications`,`annualRevenue`,`established`,`capabilities`,`matchScore` | `attributes` | + `source: 'backend'` |

## 2. 后端 `quotes.json` → `quote`

| 来源字段 | 数据库列 | 说明 |
|----------|----------|------|
| `id` | `external_id` | upsert 钥匙(如 `cmp-1`) |
| `product` | `listing_title` | 抓到的商品标题 |
| `unitPriceEur` | `price` | |
| —(固定) | `currency = 'EUR'` | |
| `deliveryLabel` | `lead_time_text` | 原文交期(如 "3–5 Werktage") |
| `deliveryDays` | `lead_time_days` | 解析出的天数 |
| `matchScore` | `score` | 排序分 |
| `vendor`,`platform`,`unitLabel`,`paymentTerm`,`paymentLabel`,`deliveryMethod`,`rating`,`reviews`,`category`,`matchScore` | `attributes` | |
| — | `product_id` / `supplier_id` | **暂留空**:vendor 名与 supplier 名对不上,待后端给出对应关系再连 |

## 3. 爬虫 (wlw) 输出 → `supplier`

| 来源字段 | 数据库列 | 说明 |
|----------|----------|------|
| `url` | `external_id` | upsert 钥匙(无 id,用公司网址) |
| `company_name` | `name` | |
| —(固定) | `origin = 'web'` | |
| `location` | `country` | |
| `contact_person` | `contact_name` | |
| `phone` | `contact_phone` | |
| `employee_count` | `scale` | |
| `source_url`,`description`,`matched_products`,`supplier_type`,`founding_year`,`delivery_range`,`certificate_count`,`score` | `attributes` | + `source: 'wlw'` |

> `"N/A"` / 空值在导入时统一忽略。

## 4. Excel 清单 → `product` / `quote` / `supplier`

| Excel 列(中/德) | 数据库列 | 说明 |
|------------------|----------|------|
| 备件名称 / Beschreibung | `product.name_zh` / `name_de` | |
| 型号 / Typ | `product.model` | |
| 货号 / Artikel-Nr. | `product.article_number` | |
| 供应商 / Lieferant | `supplier.name` | |
| 报价 / Preis | `quote.price` | |
| 参考价 / Referenzpreis | `product.reference_price` | 选定的基准价 |
| 供货周期 / Lieferzeit | `quote.lead_time_text` / `lead_time_days` | |
| 链接 / Link | `quote.source_url` | |
| FOTO / Bild | `product.photo_url` | |
| 备注 / Bemerkung | `product.notes` | |
| 安全等级(安全鞋) | `product.attributes.safety_level` | |
| MOQ / 最大采购量(行政) | `product.attributes.moq` / `max_order_qty` | |
| 制造商(设备件) | `product.attributes.manufacturer` | |

---

## 公共约定

- **upsert 钥匙**:统一用 `external_id`(后端用其 `id`,爬虫用 `url`)。重复导入只更新、不重复。
- **`origin`**:`internal` = Fuyao 老系统已有;`web` = 网上找到。
- **`attributes`**:每类特有/暂时没专列的字段,都以 `标签:值` 形式存这里;`source` 标明数据来自 `backend` / `wlw` / `excel`。
