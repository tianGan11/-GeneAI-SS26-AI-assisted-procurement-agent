import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SUPPLIERS_PATH = BASE_DIR / "data" / "suppliers.json"
QUOTES_PATH = BASE_DIR / "data" / "quotes.json"
OUTPUT_PATH = BASE_DIR / "data" / "training_examples.json"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_examples():
    suppliers = load_json(SUPPLIERS_PATH)
    quotes = load_json(QUOTES_PATH)
    
    examples = []
    
    # 类别映射字典，用于自然语言查询生成
    category_names_cn = {
        "glassAdhesive": "玻璃胶",
        "rubberSeal": "密封条",
        "waterDeflector": "挡水条",
        "glassRaw": "玻璃原片",
        "hardware": "五金件",
        "packaging": "包装材料",
        "cleaning": "清洁用品",
        "office": "办公用品",
        "safetyShoes": "安全鞋",
        "firstAid": "急救包/急救用品",
        "equipment": "气动设备/工业备件"
    }

    # 1. 基础匹配与认证匹配样例（针对每个供应商生成1-2个问题）
    for s in suppliers:
        name = s["name"]
        cat_key = s["category"]
        cat_cn = category_names_cn.get(cat_key, cat_key)
        country = s["country"]
        certs = s.get("certifications", [])
        capabilities = s.get("capabilities", [])
        
        # 模板 A：标准类目 + 国家 + 认证
        if certs:
            cert_req = certs[0]
            query_cn = f"找一家{country}的{cat_cn}供应商，必须有 {cert_req} 认证"
            examples.append({
                "query": query_cn,
                "expected_supplier": name,
                "expected_score": 95,
                "reason": f"供应商{name}位于{country}，属于{cat_cn}品类，且拥有{cert_req}认证，完全符合条件。"
            })
            
            # 英文模板
            query_en = f"Looking for a {cat_cn} supplier from {country} with {cert_req} certification"
            examples.append({
                "query": query_en,
                "expected_supplier": name,
                "expected_score": 95,
                "reason": f"Supplier {name} is based in {country}, specializes in {cat_key}, and holds {cert_req}."
            })
        
        # 模板 B：基于能力的查询
        if capabilities:
            cap = capabilities[0]
            query_cap = f"需要具有{cap}能力的{cat_cn}供应商"
            examples.append({
                "query": query_cap,
                "expected_supplier": name,
                "expected_score": 90,
                "reason": f"供应商{name}在{cat_cn}领域具备{cap}的专业核心能力。"
            })

    # 2. 价格优先 / 交期优先样例（结合 quotes 报价数据）
    # 按类别对报价进行分组
    quotes_by_cat = {}
    for q in quotes:
        cat = q.get("category")
        if cat:
            quotes_by_cat.setdefault(cat, []).append(q)

    for cat_key, cat_quotes in quotes_by_cat.items():
        cat_cn = category_names_cn.get(cat_key, cat_key)
        if len(cat_quotes) < 2:
            continue
            
        # 找到最便宜的
        cheapest = min(cat_quotes, key=lambda x: x["unitPriceEur"])
        # 找到交期最快的
        fastest = min(cat_quotes, key=lambda x: x["deliveryDays"])
        
        # 2.1 价格敏感场景
        query_price = f"我要买最便宜的{cat_cn}，预算越低越好"
        examples.append({
            "query": query_price,
            "expected_supplier": cheapest["vendor"],
            "expected_score": 90,
            "reason": f"报价单中，{cheapest['vendor']} 提供的单价为 {cheapest['unitPriceEur']} EUR 最具价格竞争力。"
        })
        
        # 2.2 紧急交期场景
        query_delivery = f"紧急采购{cat_cn}，交期越快越好，要求3天内到货"
        examples.append({
            "query": query_delivery,
            "expected_supplier": fastest["vendor"],
            "expected_score": 92,
            "reason": f"该供应商交期仅为 {fastest['deliveryDays']} 天，最能满足紧急到货要求。"
        })

    # 随机打乱并限制数量在 40-50 个左右以保证多样性和质量
    random.seed(42)
    random.shuffle(examples)
    
    # 去重（通过query）
    seen_queries = set()
    unique_examples = []
    for ex in examples:
        if ex["query"] not in seen_queries:
            seen_queries.add(ex["query"])
            unique_examples.append(ex)
            
    # 输出到 JSON
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_examples[:50], f, ensure_ascii=False, indent=2)
        
    print(f"成功生成了 {len(unique_examples[:50])} 条训练样例，并已写入 {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_examples()
