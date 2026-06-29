from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.procurement_agent import ProcurementAgent  # noqa: E402


SCENARIOS = [
    {
        "query": "A4 打印纸 80g",
        "expected_category": "paper",
        "required_terms": ["a4", "papier"],
        "forbidden_terms": ["ordner", "etikett", "laminier", "trennstreifen", "folder", "binder"],
    },
    {
        "query": "Kopierpapier A4 80g",
        "expected_category": "paper",
        "required_terms": ["a4", "papier"],
        "forbidden_terms": ["ordner", "etikett", "laminier", "trennstreifen", "folder", "binder"],
    },
    {
        "query": "笔记本电脑 ThinkPad",
        "expected_category": "laptop",
        "forbidden_terms": ["rivet", "rivkle", "dock", "headset", "monitor", "hülle", "sleeve", "tasche", "ständer", "stand"],
    },
    {
        "query": "显示器 27寸",
        "expected_category": "monitor",
        "forbidden_terms": ["dock", "laptop", "paper"],
    },
    {
        "query": "HP Thunderbolt Dock 扩展坞",
        "expected_category": "accessory",
        "required_terms": ["dock"],
        "forbidden_terms": ["elitebook", "thinkpad", "notebook", "rivkle", "bitpanda", "dockers", "chinos", "khakis", "crypto", "kurs"],
    },
    {
        "query": "iPhone 手机 64GB",
        "expected_category": "phone",
        "required_terms": ["iphone"],
        "forbidden_terms": ["dock", "headset", "laptop", "ladegerät", "charger", "adapter", "kabel", "cable", "hülle", "case"],
    },
    {
        "query": "安全鞋 S3 42码",
        "expected_category": "safetyShoes",
        "required_terms": ["s3"],
        "forbidden_terms": ["paper", "dock", " sport s1"],
    },
    {
        "query": "气动接头 Festo QS 6",
        "expected_category": "equipment",
        "required_terms": ["steck"],
        "forbidden_terms": ["schalldämpfer", "drossel", "rückschlagventil", "steckschlüssel", "ratschen", "verlängerungskabel"],
    },
    {
        "query": "文件夹 DIN A4",
        "expected_category": "office",
        "required_terms": ["ordner"],
        "forbidden_terms": ["kopierpapier", "druckerpapier", "laminier", "etikett"],
    },
    {
        "query": "洗洁精 1L",
        "expected_category": "cleaning",
        "required_terms": ["spülmittel"],
        "forbidden_terms": ["ordner", "dock", "schwämme", "wc-reiniger", "spülmaschinensalz", "klarspüler"],
    },
]


def _row_text(row: dict) -> str:
    return " ".join(str(row.get(k) or "") for k in ("product", "vendor", "platform", "description", "category")).lower()


async def run_regression() -> None:
    agent = ProcurementAgent()
    failures: list[str] = []
    for scenario in SCENARIOS:
        result = await agent.search_quotes(scenario["query"])
        top = result["results"][:3]
        top_text = " | ".join(_row_text(row) for row in top)
        product_text = " | ".join(str(row.get("product") or "").lower() for row in top)
        categories = [row.get("category") for row in top]
        if scenario["expected_category"] not in categories and result["intent"].get("category") != scenario["expected_category"]:
            failures.append(
                f"{scenario['query']}: expected category {scenario['expected_category']} in intent/top3, got intent={result['intent']} top={categories}"
            )
        for term in scenario.get("required_terms", []):
            if term.lower() not in top_text:
                failures.append(f"{scenario['query']}: required term missing from top3: {term}\nTOP={top_text}")
        for term in scenario.get("forbidden_terms", []):
            if term.lower() in product_text:
                failures.append(f"{scenario['query']}: forbidden term leaked into top3 product titles: {term}\nTOP={product_text}")
        print(f"QUERY={scenario['query']} INTENT={result['intent']} TOP={[row.get('product') for row in top]}")

    if failures:
        raise AssertionError("\n".join(failures))
    print(f"PASS {len(SCENARIOS)}/{len(SCENARIOS)} search regression scenarios")


if __name__ == "__main__":
    asyncio.run(run_regression())
