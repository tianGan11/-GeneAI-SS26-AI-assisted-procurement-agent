# 采购 Agent 数据库 · 表结构说明（给小组成员）

> 一句话:这个库把**“想买的东西”**和**“找到的报价/供应商”**分开存,
> 报价只增不改(留下价格历史),支持两条工作流:
> **找供应商(sourcing)** 和 **比价(quote)**。

## 大图:数据怎么流动

1. 采购需求进来 → `procurement_request`(+ 明细 `request_item`)
2. 要买的东西 → `product`(按 `category` 归类)
3. 去找供应商(workflow 1)→ `sourcing_session` + `sourcing_candidate`
4. 去各网站比价(workflow 2)→ 爬虫/后端写 `quote`(每条报价一行,带抓取时间 = 价格历史)
5. 人工/系统选定 → 记到 `feedback`,最终采用记到 `purchase_history`
6. 汇总导出 → `report`

---

## 每张表

| 表 | 中文 | 作用 | 关键字段 |
|----|------|------|----------|
| `category` | 分类 | 商品分类,支持父子层级 | `name_de` / `name_zh` / `parent_id` |
| `supplier` | 供应商 | 所有供应商 | `origin`(internal=老系统已有 / web=网上找到)、`external_id`(upsert 钥匙) |
| `product` | 产品 | 想买的东西,一个一行 | `name`、`model`、`article_number`、`reference_price`、`attributes` |
| `procurement_request` | 采购请求 | 一次采购任务/需求 | `request_text`、`status` |
| `request_item` | 请求明细 | 一次请求里的每个条目 | `product_id`、`quantity` |
| `quote` | 报价 | 找到的每条报价(只增不改) | `price`、`lead_time_*`、`source_url`、`captured_at`、`external_id` |
| `sourcing_session` | 寻源任务 | 一次“找供应商”搜索 | `need_text`、`region_filter` |
| `sourcing_candidate` | 候选供应商 | 寻源找出的候选 | `relevance`、`is_incumbent` |
| `report` | 报告 | 导出的成品文件 | `format`、`file_path` |
| `feedback` | 反馈 | 人对结果的采纳/否决 | `approved`、`comment` |
| `purchase_history` | **采购历史(新)** | 每次最终采用了哪家供应商 | `product_id`、`supplier_id`、`price`、`purchased_at` |

**视图 `v_product_best_quote`**:每个产品挑出“最优/选定”那条报价,是给采购看的比价结果雏形。

---

## 两个设计要点(常被问)

**为什么 product 和 quote 要分开?**
Excel 里“一个物料 + 三家比价 + 参考价”挤在一行;数据库里拆开——一个物料一行(`product`),它的每条报价单独一行(`quote`)。这样才能留下价格历史、做趋势和基准。

**品类字段不一样怎么办(安全鞋有安全等级、清洁用品有 MOQ)?**
共用字段做成真实列;每类特有的零碎字段塞进 `attributes`(JSONB,一格里装“标签:值”)。

---

## 关于“历史供应商”

- **老系统已有的供应商** → 导进 `supplier`,把 `origin` 设成 `internal` 即可(无需新表);可在 `attributes` 标 `source: 'fuyao_legacy'`。
- **每次最终采用的供应商** → 记进新表 `purchase_history`,每采用一次一行。
  能回答:这个东西历史上都从谁买、价格怎么变、最常用哪家 → 给排序“优先用过且靠谱的供应商”。
