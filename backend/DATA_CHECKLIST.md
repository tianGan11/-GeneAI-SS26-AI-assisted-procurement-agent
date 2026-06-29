# 📋 ProcureAI Agent 数据需求清单

> 发给组员的数据收集模板 | 2026-06-15

---

## 🔴 第一优先：必须数据（没这些 Agent 无法工作）

### ① 供应商数据（目标 20-30 家，每品类 3-5 家）

请在下方 Excel 模板中填写：

| 字段 | 说明 | 示例 |
|------|------|------|
| 供应商名称 | 公司全名 | Henkel AG & Co. KGaA |
| 品类 | 选一个：玻璃胶 / 挡水条 / 密封条 / 玻璃原片 / 五金 / 包装 | 玻璃胶 |
| 国家 | 英文 | Germany |
| 城市 | 英文 | Düsseldorf |
| 描述 | 2-3句话，这家供应商做什么、核心优势（最重要！用于AI匹配） | 全球胶粘剂领导者，汽车挡风玻璃聚氨酯胶，免底涂直粘系统，OEM认证 |
| 主要产品 | 逗号分隔 | Teroson PU 8597, SikaTack MOVE IT |
| 认证 | 逗号分隔 | IATF 16949, ISO 9001, ISO 14001 |
| 联系人 | 姓名 | Markus Bauer |
| 电话 | 国际格式 | +49 211 797 0 |
| 邮箱 | - | automotive@henkel.com |
| 网站 | 不带https:// | www.henkel-adhesives.com |
| 员工规模 | 范围 | 50000+ |
| 年收入 | 范围 | € 22B+ |
| 成立年份 | 数字 | 1876 |
| 核心能力 | 逗号分隔，3-5个关键词 | 聚氨酯粘合, 免底涂直粘, 结构粘接 |

**已有（不需要重复填）：**
- Henkel AG (玻璃胶, 德国)
- Sika Automotive (玻璃胶, 德国)
- CQLT SaarGummi (密封条, 德国)
- Cooper Standard France (挡水条, 法国)
- Şişecam Automotive (玻璃原片, 意大利)
- Wilhelm Böllhoff (五金, 德国)
- DS Smith Packaging (包装, 德国)

---

### ② 产品报价数据（目标 30-50 条，每品类 5-10 条）

| 字段 | 说明 | 示例 |
|------|------|------|
| 供应商 | 公司名 | Würth Industrie |
| 平台 | 报价来源 | Würth Online-Shop |
| 产品名 | 完整产品名 | SikaTack MOVE IT — 挡风玻璃胶 400ml |
| 品类 | 选一个 | 玻璃胶 |
| 单价(€) | 纯数字 | 13.90 |
| 单位 | per piece / per meter / per carton | per piece |
| 交期(天) | 纯数字（营业日） | 2 |
| 交期描述 | 原始描述 | 1-2 Werktage |
| 付款方式 | onAccount / prepayment / card | card |
| 付款描述 | 原始描述 | Credit Card / PayPal |
| 配送方式 | - | UPS Standard |
| 评分 | 1-5 | 4.6 |
| 评价数 | 数字 | 89 |
| 链接 | 原始URL | https://... |

---

## 🟡 第二优先：训练数据（让 Agent 变聪明）

### ③ 搜索需求 → 期望结果配对（目标 30-50 条，每人写 10-15 条）

格式：
```
需求：用自然语言写的采购需求
期望Top3供应商（按优先级排序）

---

需求: "我要找德国的挡水条供应商，IATF认证，交期不超过7天"
  期望Top1: Cooper Standard France SAS（挡水条专业，IATF认证，法国就近）
  期望Top2: CQLT SaarGummi Technologies（密封条相关品类）
  期望Top3: 其他密封条/挡水条类供应商

需求: "最便宜的挡风玻璃胶，紧急3天内到货"
  期望Top1: Würth Industrie（2天到货，价格适中）
  期望Top2: Henkel Direct（价格最低€11.40但4天到货，降分）
  
需求: "汽车玻璃安装用的结构胶和底涂剂，IATF认证"
  期望Top1: Henkel AG（PU胶+底涂剂全套，IATF认证）
  期望Top2: Sika Automotive（结构胶方案）

... 每人写 10-15 条，覆盖不同品类、不同需求角度 ...
```

**写的时候注意覆盖这些角度：**
- 不同品类（玻璃胶 / 挡水条 / 密封条 / 玻璃原片 / 五金 / 包装）
- 不同约束（价格敏感 / 交期优先 / 认证必须 / 综合考量）
- 不同语言输入（中文 / 英文 / 中英混合）
- 不同地区偏好（德国优先 / 不限 / 全欧洲）
- 极端情况（"什么都不限，列出所有" / "非常严格的条件，可能没有匹配"）

---

### ④ 供应商质量评分参考（每家一份，懂供应链的人写）

```
Henkel AG & Co. KGaA:
  行业地位: 5/5 — 全球胶粘剂第一
  价格竞争力: 3/5 — 贵但质量顶级
  交付可靠性: 4/5 — 大厂流程规范
  创新能力: 5/5 — 持续研发投入
  适合场景: 高端OEM项目、认证要求严格的订单、大批量长期合作

Sika Automotive GmbH:
  行业地位: 4/5 — 建筑+汽车胶粘剂双线
  价格竞争力: 3/5 — 与Henkel接近
  交付速度: 4/5 — 欧洲物流网络成熟
  适合场景: 中高端项目、需要本地技术支持

... 每家供应商一份 ...
```

---

## 🟢 第三优先：加分项

### ⑤ 中英德品类关键词映射

| 中文 | English | Deutsch | 品类Key |
|------|---------|---------|---------|
| 挡水条 | water deflector | Wasserabweiser | waterDeflector |
| 玻璃胶 | glass adhesive / urethane | Glas-Klebstoff | glassAdhesive |
| 密封条 | rubber seal / weatherstrip | Dichtungsprofil | rubberSeal |
| 玻璃原片 | float glass / raw glass | Floatglas | glassRaw |
| 五金件 | hardware / fasteners | Beschläge | hardware |
| 包装材料 | packaging | Verpackung | packaging |

---

### ⑥ 历史采购决策记录（如果有的话）

```
格式:
"2024年Q3采购挡水条，预算€10/m以内 → 选了Cooper Standard → 
原因: 交期稳定(4周内)、本地技术支持响应快、价格在预算内"
```
