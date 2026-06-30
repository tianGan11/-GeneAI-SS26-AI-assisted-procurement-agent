from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.parser import ProcurementIntent
from agent.retriever import SupplierRetriever


class FakeWebResearcher:
    called_with = []

    def __init__(self, llm=None):
        self.llm = llm

    async def research(self, intent, max_suppliers=8, progress=None):
        self.__class__.called_with.append((intent, max_suppliers))
        return [
            {
                "id": "web-viking",
                "name": "Viking Office Deutschland",
                "category": "office",
                "country": "Germany",
                "description": "Office supplies supplier",
                "products": ["A4 Papier"],
                "certifications": [],
                "capabilities": ["Bürobedarf"],
                "website": "https://www.viking.de/",
                "matchScore": 80,
                "source": "web-research-fallback",
            }
        ]


class RetrieverWebResearchIntegrationTest(unittest.TestCase):
    def test_better_web_supplier_can_outrank_database_supplier_after_bonus_reduction(self):
        local_results = [{
            "id": "db-office",
            "name": "Existing Database Office Supplier",
            "matchScore": 74,
            "source": "database",
        }]
        web_results = [{
            "id": "web-office",
            "name": "New Web Office Supplier",
            "matchScore": 82,
            "source": "web-research-llm",
        }]

        merged = SupplierRetriever._merge_results(local_results, web_results)

        self.assertEqual(merged[0]["id"], "web-office")
        self.assertEqual(merged[1]["id"], "db-office")
        self.assertEqual(merged[1]["source"], "database")
        self.assertEqual(merged[1]["repurchasePriority"], "database")

    def test_web_supplier_can_still_win_when_score_gap_is_large(self):
        local_results = [{
            "id": "db-weak",
            "name": "Weak Existing Supplier",
            "matchScore": 45,
            "source": "database",
        }]
        web_results = [{
            "id": "web-strong",
            "name": "Strong Web Supplier",
            "matchScore": 90,
            "source": "web-research-llm",
        }]

        merged = SupplierRetriever._merge_results(local_results, web_results)

        self.assertEqual(merged[0]["id"], "web-strong")

    def test_low_quality_local_results_are_hidden_while_web_results_remain(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "Papier"])
        local_supplier = {
            "id": "local-seal",
            "name": "TEST_Sika Automotive GmbH",
            "category": "glassAdhesive",
            "country": "Germany",
            "description": "Automotive adhesive supplier",
            "products": ["glass adhesive"],
            "certifications": [],
            "capabilities": [],
            "matchScore": 30,
        }
        retriever = SupplierRetriever(None, [local_supplier])

        with patch("agent.retriever.WebResearcher", FakeWebResearcher):
            results = asyncio.run(retriever.search(intent, top_k=5))

        self.assertEqual(FakeWebResearcher.called_with[-1][1], 8)
        self.assertEqual(results[0]["name"], "Viking Office Deutschland")
        self.assertEqual(results[0]["source"], "web-research-fallback")
        self.assertFalse(any(item["id"] == "local-seal" for item in results))
        self.assertTrue(all(item["matchScore"] >= 60 for item in results))


if __name__ == "__main__":
    unittest.main()
