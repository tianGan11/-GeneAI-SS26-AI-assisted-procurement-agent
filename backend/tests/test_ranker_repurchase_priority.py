from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.ranker import LLMRanker


class RankerRepurchasePriorityTest(unittest.TestCase):
    def test_database_supplier_gets_repurchase_bonus_when_scores_are_close(self):
        ranker = LLMRanker(llm=None)
        candidates = [
            {
                "id": "db-office",
                "name": "Existing Database Office Supplier",
                "category": "office",
                "country": "Germany",
                "description": "A4 paper folders office supplier",
                "products": ["A4 paper", "folders"],
                "capabilities": ["B2B wholesale"],
                "matchScore": 74,
                "source": "database",
                "repurchasePriority": "database",
            },
            {
                "id": "web-office",
                "name": "New Web Office Supplier",
                "category": "office",
                "country": "Germany",
                "description": "A4 paper folders office supplier",
                "products": ["A4 paper", "folders"],
                "capabilities": ["B2B wholesale"],
                "matchScore": 82,
                "source": "web-research-llm",
            },
        ]

        ranked = asyncio.run(ranker.rank_suppliers("A4 paper folders office Germany", candidates))

        self.assertEqual(ranked[0]["id"], "db-office")


if __name__ == "__main__":
    unittest.main()
