from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.parser import ProcurementIntent
from web_research.researcher import SearchResult, WebResearcher


class FakeSearchProvider:
    def __init__(self, by_query: dict[str, list[SearchResult]]):
        self.by_query = by_query
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        self.queries.append(query)
        return self.by_query.get(query, [])[:max_results]


class FakePageFetcher:
    async def fetch_text(self, url: str) -> str:
        fixtures = {
            "https://www.viking.de/": "Viking Bürobedarf A4 Papier Ordner Druckerzubehör Deutschland B2B supplier",
            "https://www.office.com/": "Microsoft Office 365 login sign in Outlook",
            "https://www.otto-office.com/de/": "OTTO Office Bürobedarf Bürotechnik Büromöbel Kopierpapier Deutschland",
        }
        return fixtures.get(url, "")


class WebResearcherTest(unittest.TestCase):
    def test_plans_category_specific_queries_and_excludes_microsoft_noise(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "Papier"])
        researcher = WebResearcher(search_provider=FakeSearchProvider({}), page_fetcher=FakePageFetcher())

        queries = researcher.plan_queries(intent)

        joined = "\n".join(queries).lower()
        self.assertGreaterEqual(len(queries), 5)
        self.assertIn("bürobedarf", joined)
        self.assertIn("site:wlw.de", joined)
        self.assertIn("site:europages", joined)
        self.assertIn("-microsoft", joined)
        self.assertNotIn("automotive supplier", joined)

    def test_collects_filters_extracts_and_falls_back_to_structured_suppliers(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "Papier", "Ordner"])
        query_probe = WebResearcher(search_provider=FakeSearchProvider({}), page_fetcher=FakePageFetcher()).plan_queries(intent)[0]
        provider = FakeSearchProvider({
            query_probe: [
                SearchResult(title="Office 365 login", url="https://www.office.com/", snippet="Microsoft login"),
                SearchResult(title="Viking Office Deutschland Bürobedarf", url="https://www.viking.de/", snippet="A4 Papier Ordner supplier"),
                SearchResult(title="OTTO Office Bürobedarf", url="https://www.otto-office.com/de/", snippet="Kopierpapier Büromaterial"),
            ]
        })
        researcher = WebResearcher(search_provider=provider, page_fetcher=FakePageFetcher())

        suppliers = asyncio.run(researcher.research(intent, max_suppliers=5))

        names = [item["name"] for item in suppliers]
        websites = [item["website"] for item in suppliers]
        self.assertIn("Viking Office Deutschland Bürobedarf", names)
        self.assertIn("OTTO Office Bürobedarf", names)
        self.assertNotIn("https://www.office.com/", websites)
        self.assertGreaterEqual(len(suppliers), 4)  # search hits + fallback seeds
        self.assertTrue(all(item["category"] == "office" for item in suppliers))
        self.assertTrue(all(item["source"] in {"web-research", "web-research-fallback"} for item in suppliers))
        self.assertTrue(all("microsoft" not in item["website"].lower() for item in suppliers))

    def test_detects_noisy_or_blocked_pages(self):
        researcher = WebResearcher(search_provider=FakeSearchProvider({}), page_fetcher=FakePageFetcher())
        self.assertTrue(researcher.is_noisy_or_blocked("Request unsuccessful. Incapsula incident ID: 123"))
        self.assertTrue(researcher.is_noisy_or_blocked("use strict function(t) return t"))
        self.assertFalse(researcher.is_noisy_or_blocked("German office-supplies supplier for paper and folders"))

    def test_filters_generic_b2b_marketplace_homepages(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["Bürobedarf"])
        researcher = WebResearcher(search_provider=FakeSearchProvider({}), page_fetcher=FakePageFetcher())
        generic_homepage = SearchResult(
            title="europages – Der B2B-Marktplatz für Lieferanten und Einkäufer",
            url="https://www.europages.de/",
            snippet="B2B marketplace for buyers and sellers",
        )
        supplier_page = SearchResult(
            title="Bürobedarf Müller GmbH - Lieferant auf europages",
            url="https://www.europages.de/BUEROBEDARF-MUELLER/000000.html",
            snippet="A4 Papier Ordner Bürobedarf Lieferant Deutschland",
        )
        self.assertFalse(researcher.is_relevant_result(generic_homepage, intent))
        self.assertTrue(researcher.is_relevant_result(supplier_page, intent))

    def test_filters_consumer_marketplaces_and_social_product_pages(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["Ordner"])
        researcher = WebResearcher(search_provider=FakeSearchProvider({}), page_fetcher=FakePageFetcher())
        blocked_results = [
            SearchResult("HERMA Ordner A4", "https://www.amazon.de/HERMA-Ordner/dp/B09MQY2PT7", "A4 Ordner"),
            SearchResult("Biella Ordner Minimal Design A4", "https://de.pinterest.com/pin/258323728618087480/", "Ordner Bürobedarf"),
            SearchResult("Ordner gebraucht kaufen", "https://www.ebay.de/itm/123", "office folder"),
            SearchResult("OTTO Office Anzeige", "https://www.bing.com/aclick?u=otto-office", "Bürobedarf Anzeige"),
            SearchResult("Office folder wholesale", "https://www.alibaba.com/showroom/office-folder-size.html", "Office Supplies"),
            SearchResult("Printer Supplies Bilder", "https://stock.adobe.com/search?k=printer+supplies", "stock photos"),
            SearchResult("Web supplier", "/clev?event=StartpageResultClick", "Office supplies"),
            SearchResult("纸制品市场规模、行业份额", "https://www.fortunebusinessinsights.com/zh/paper-products-market-106150", "market report"),
            SearchResult("Deutsche Post", "https://www.deutschepost.de/", "Geschäftspost und Büromaterial"),
            SearchResult("Bilingual Visual Dictionary", "https://www.scribd.com/document/682137409/Bilingual-Visual-Dictionary", "office equipment vocabulary"),
            SearchResult("Chinese vocabulary", "https://fliphtml5.com/cialx/zxmp/Chinese_vocabulary/", "office supplies words"),
            SearchResult("stationery translation", "https://context.reverso.net/übersetzung/englisch-chinesisch/stationery", "translation context"),
            SearchResult("Files: Law and Media Technology", "https://monoskop.org/images/file.pdf", "office technology papers"),
            SearchResult("Ordner mit Gummiband A4", "https://sostrenegrene.com/de/produkte/buerobedarf/ordner", "1 Stck"),
        ]
        for result in blocked_results:
            self.assertFalse(researcher.is_relevant_result(result, intent), result.url)
        supplier_result = SearchResult(
            "Viking Bürobedarf",
            "https://www.viking.de/",
            "Bürobedarf, Papier, Ordner und B2B office supplies supplier",
        )
        self.assertTrue(researcher.is_relevant_result(supplier_result, intent))


if __name__ == "__main__":
    unittest.main()
