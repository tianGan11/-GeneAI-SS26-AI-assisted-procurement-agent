from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.parser import IntentParser, ProcurementIntent


class ParserTest(unittest.TestCase):
    def test_english_office_supplies_are_parsed_as_office(self):
        parser = IntentParser(llm=None)
        intent = asyncio.run(
            parser.parse("A4 paper and folders, German supplier, delivery within 7 days, budget 500 EUR")
        )
        self.assertEqual(intent.category, "office")
        self.assertEqual(intent.country, "Germany")
        self.assertEqual(intent.max_price, 500)
        self.assertEqual(intent.max_delivery_days, 7)

    def test_invalid_llm_category_falls_back_to_heuristic_category(self):
        parser = IntentParser(llm=None)
        merged = parser._merge_with_heuristics(
            "A4 paper and folders, German supplier",
            ProcurementIntent(category="general procurement", country=None, keywords=[]),
        )
        self.assertEqual(merged.category, "office")
        self.assertEqual(merged.country, "Germany")


if __name__ == "__main__":
    unittest.main()
