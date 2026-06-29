from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.parser import ProcurementIntent
from agent.procurement_agent import ProcurementAgent
from web_research.researcher import PageSnapshot, SearchResult
from web_research.researcher import StaticPageFetcher


class FakeQuoteSearchProvider:
    def __init__(self):
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        self.queries.append(query)
        if len(self.queries) == 1:
            return [
                SearchResult(
                    title="A4 Kopierpapier online kaufen",
                    url="https://paper-shop.example/a4-paper",
                    snippet="A4 Papier für Bürobedarf",
                )
            ]
        return [
            SearchResult(
                title="A4 Papier 500 Blatt € 4,99",
                url="https://second-shop.example/a4-paper",
                snippet="Büropapier A4 online shop Deutschland",
            )
        ]


class FakeQuotePageFetcher:
    async def fetch_page(self, url: str) -> PageSnapshot:
        return PageSnapshot(
            url=url,
            text="A4 Kopierpapier 500 Blatt Packung. Sofort lieferbar. Preis € 5,49 inkl. MwSt.",
            links=[],
        )


class QuotePriceDiscoveryTest(unittest.TestCase):
    def test_web_quote_opens_product_page_and_extracts_price(self):
        async def scenario():
            agent = ProcurementAgent.__new__(ProcurementAgent)
            agent.quote_search_provider = FakeQuoteSearchProvider()
            agent.quote_page_fetcher = FakeQuotePageFetcher()
            intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "Papier"])

            results = await agent._search_web_quotes("A4 Papier 500 Blatt", intent, max_results=3)

            self.assertGreaterEqual(len(results), 1)
            self.assertTrue(any(item["unitPriceEur"] == 5.49 for item in results), results)
            self.assertTrue(all(item["unitLabel"] != "需人工核价" for item in results), results)
            self.assertGreaterEqual(len(agent.quote_search_provider.queries), 2)

        asyncio.run(scenario())

    def test_priced_candidates_hide_manual_price_rows_when_prices_exist(self):
        candidates = [
            {"id": "manual", "unitPriceEur": None, "unitLabel": "需人工核价"},
            {"id": "priced", "unitPriceEur": 12.5, "unitLabel": "€ 12.50"},
        ]

        filtered = ProcurementAgent._prefer_priced_quote_candidates(candidates)

        self.assertEqual([item["id"] for item in filtered], ["priced"])

    def test_price_parser_handles_common_german_price_formats(self):
        self.assertEqual(ProcurementAgent._extract_eur_price("Preis € 1.234,56"), 1234.56)
        self.assertEqual(ProcurementAgent._extract_eur_price("nur 4,99 EUR"), 4.99)
        self.assertEqual(ProcurementAgent._extract_eur_price("ab € 25,-"), 25.0)

    def test_static_fetcher_preserves_json_ld_price_fragments(self):
        html = (
            '<html><head>'
            '<script type="application/ld+json">'
            '{"@type":"Product","offers":{"price":"7.49","priceCurrency":"EUR"}}'
            '</script>'
            '</head><body><h1>A4 Kopierpapier 500 Blatt</h1></body></html>'
        )

        page = StaticPageFetcher()._parse_html("https://shop.example/product", html)
        self.assertIn("7.49", page.text)
        self.assertEqual(ProcurementAgent._extract_eur_price(page.text), 7.49)

    def test_a4_paper_relevance_rejects_generic_a4_and_calculators(self):
        intent = ProcurementIntent(category="hardware", country="Germany", keywords=["a4纸"])

        self.assertTrue(
            ProcurementAgent._is_relevant_quote_item(
                {"product": "Inapa tecno Kopierpapier DIN A4 80 g/qm 500 Blatt", "unitPriceEur": 9.21},
                "我需要a4纸",
                intent,
            )
        )
        self.assertFalse(
            ProcurementAgent._is_relevant_quote_item(
                {"product": "Schnellhefter Plastik A4 （ab 50 stk）", "unitPriceEur": 0.30},
                "我需要a4纸",
                intent,
            )
        )
        self.assertFalse(
            ProcurementAgent._is_relevant_quote_result(
                "Preis je Menge vergleichen und berechnen Stückpreis Rechner € 3,50",
                "我需要a4纸",
                intent,
                price_found=True,
            )
        )

    def test_generic_product_relevance_does_not_cross_match_other_products(self):
        cases = [
            (
                "我需要鼠标",
                ProcurementIntent(category="hardware", country="Germany", keywords=["鼠标"]),
                {"product": "Logitech B100 Maus mit Kabel USB optischer Sensor", "unitPriceEur": 3.48},
                {"product": "Hama Tastatur mit Kabel QWERTZ schwarz", "unitPriceEur": 9.24},
            ),
            (
                "我需要键盘",
                ProcurementIntent(category="hardware", country="Germany", keywords=["键盘"]),
                {"product": "Hama Tastatur mit Kabel QWERTZ schwarz", "unitPriceEur": 9.24},
                {"product": "Logitech B100 Maus mit Kabel USB optischer Sensor", "unitPriceEur": 3.48},
            ),
            (
                "我需要计算器",
                ProcurementIntent(category="hardware", country="Germany", keywords=["计算器"]),
                {"product": "Canon Taschenrechner AS-2200", "unitPriceEur": 15.39},
                {"product": "Preis je Menge vergleichen und berechnen", "unitPriceEur": 3.50},
            ),
        ]

        for query, intent, good, bad in cases:
            with self.subTest(query=query):
                self.assertTrue(ProcurementAgent._is_relevant_quote_item(good, query, intent), good)
                self.assertFalse(ProcurementAgent._is_relevant_quote_item(bad, query, intent), bad)

    def test_web_search_query_is_product_focused_and_noise_is_blocked(self):
        intent = ProcurementIntent(category="hardware", country="Germany", keywords=["a4纸"])

        self.assertEqual(
            ProcurementAgent._quote_search_product_phrase("我需要a4纸", intent),
            "a4 kopierpapier",
        )
        self.assertTrue(ProcurementAgent._is_blocked_quote_domain("euroshop-online.de"))
        self.assertTrue(ProcurementAgent._is_blocked_quote_domain("shop.deutschepost.de"))
        self.assertTrue(
            ProcurementAgent._is_quote_noise_result(
                "Preis je Menge vergleichen und berechnen Stückpreis Rechner € 3,50",
                "https://rechneronline.de/matrix/preis-je-menge.php",
            )
        )


if __name__ == "__main__":
    unittest.main()
