# suppliers.json Schema for ProcureAI

## 格式说明

每个供应商一个 JSON 对象，所有对象放在一个数组 `[]` 里。

## 模板

```json
[
  {
    "id": "sup-henkel-001",
    "name": "Henkel AG & Co. KGaA",
    "category": "glassAdhesive",
    "country": "Germany",
    "city": "Düsseldorf",
    "description": "供应商简介，2-3句话描述做什么、核心优势（重要！用于AI语义匹配）",
    "products": ["Teroson PU 8597 HMLC", "Primer 207 Glass Activator"],
    "certifications": ["IATF 16949", "ISO 9001"],
    "contactPerson": "Markus Bauer",
    "phone": "+49 211 797 0",
    "email": "automotive@henkel.com",
    "website": "www.henkel-adhesives.com",
    "employees": "50000+",
    "annualRevenue": "€ 22B+",
    "established": 1876,
    "capabilities": ["Polyurethane adhesives", "OEM-approved cure profiles"],
    "matchScore": 70
  }
]
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | ✅ | 唯一ID，格式: `sup-{名称缩写}-{序号}` |
| name | string | ✅ | 公司全名 |
| category | string | ✅ | 品类，必须是以下之一：glassAdhesive / rubberSeal / waterDeflector / glassRaw / hardware / packaging / cleaning / office / safetyShoes / firstAid / equipment |
| country | string | ✅ | 英文国名 |
| city | string | ❌ | 城市（可空 `""`） |
| description | string | ✅ | 2-3句话简介（最重要❗用于AI匹配） |
| products | array | ✅ | 产品列表，3-5个主要产品名 |
| certifications | array | ❌ | 认证列表（可空 `[]`） |
| contactPerson | string | ❌ | 联系人（可空 `""`） |
| phone | string | ❌ | 电话（可空 `""`） |
| email | string | ❌ | 邮箱（可空 `""`） |
| website | string | ❌ | 网站（可空 `""`） |
| employees | string | ❌ | 员工规模（可空 `""`） |
| annualRevenue | string | ❌ | 年收入（可空 `""`） |
| established | number | ❌ | 成立年份（未知填 0） |
| capabilities | array | ❌ | 核心能力关键词（可用 products 代替） |
| matchScore | number | ✅ | 填 70 就行，后端会重新打分 |

## 品类对照

| 英文key | 中文 |
|---------|------|
| glassAdhesive | 玻璃胶 |
| rubberSeal | 密封条 |
| waterDeflector | 挡水条 |
| glassRaw | 玻璃原片 |
| hardware | 五金/IT硬件 |
| packaging | 包装 |
| cleaning | 清洁用品 |
| office | 办公用品 |
| safetyShoes | 安全鞋 |
| firstAid | 急救用品 |
| equipment | 设备物料 |

## 注意事项

1. `matchScore` 填 70 就行，不用算，后端 Agent 会重新打分
2. `description` 是最重要的字段，尽量写清楚公司做什么
3. 能抓到的就填，抓不到的就空字符串 `""` 或空数组 `[]`
4. 如果有价格信息，另外存一个文件，格式我发你
5. 输出文件名: `suppliers_scraped.json`
