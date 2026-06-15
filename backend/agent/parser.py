from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field


class ProcurementIntent(BaseModel):
    category: Optional[str] = None
    country: Optional[str] = None
    certifications: list[str] = Field(default_factory=list)
    max_price: Optional[float] = None
    max_delivery_days: Optional[int] = None
    keywords: list[str] = Field(default_factory=list)


CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "glassAdhesive": {
        "glass adhesive",
        "windshield adhesive",
        "windscreen adhesive",
        "urethane",
        "polyurethane",
        "terason",
        "teroson",
        "sikatack",
        "玻璃胶",
        "挡风玻璃胶",
        "结构胶",
        "klebstoff",
        "glas-klebstoff",
        "scheibenkleber",
    },
    "rubberSeal": {
        "rubber seal",
        "weatherstrip",
        "seal",
        "sealing profile",
        "epdm",
        "密封条",
        "dichtungsprofil",
        "dichtung",
    },
    "waterDeflector": {
        "water deflector",
        "beltline",
        "water shield",
        "挡水条",
        "wasserabweiser",
    },
    "glassRaw": {
        "float glass",
        "raw glass",
        "automotive glass",
        "玻璃原片",
        "floatglas",
    },
    "hardware": {
        "hardware",
        "fastener",
        "rivet",
        "bolt",
        "nut",
        "五金",
        "beschläge",
        "befestigung",
    },
    "packaging": {
        "packaging",
        "box",
        "carton",
        "corrugated",
        "包装",
        "verpackung",
    },
}

COUNTRY_ALIASES = {
    "germany": "Germany",
    "deutschland": "Germany",
    "德国": "Germany",
    "france": "France",
    "frankreich": "France",
    "法国": "France",
    "italy": "Italy",
    "italien": "Italy",
    "意大利": "Italy",
    "europe": "Europe",
    "eu": "Europe",
    "欧洲": "Europe",
}


class IntentParser:
    def __init__(self, llm):
        self.llm = llm

    async def parse(self, query: str) -> ProcurementIntent:
        prompt = (
            "Extract procurement search intent from the user's Chinese, English, or German query. "
            "Identify category using one of: glassAdhesive, rubberSeal, waterDeflector, "
            "glassRaw, hardware, packaging. Extract country, required certifications, "
            "maximum unit price in EUR, maximum delivery days, and concise search keywords. "
            f"Query: {query}"
        )

        if self.llm is not None and hasattr(self.llm, "with_structured_output"):
            try:
                structured_llm = self.llm.with_structured_output(ProcurementIntent)
                result = await structured_llm.ainvoke(prompt)
                if isinstance(result, ProcurementIntent):
                    return self._merge_with_heuristics(query, result)
                return self._merge_with_heuristics(query, ProcurementIntent.model_validate(result))
            except Exception:
                pass

        return self._parse_heuristically(query)

    def _merge_with_heuristics(self, query: str, intent: ProcurementIntent) -> ProcurementIntent:
        heuristic = self._parse_heuristically(query)
        return ProcurementIntent(
            category=intent.category or heuristic.category,
            country=intent.country or heuristic.country,
            certifications=list(dict.fromkeys([*intent.certifications, *heuristic.certifications])),
            max_price=intent.max_price if intent.max_price is not None else heuristic.max_price,
            max_delivery_days=intent.max_delivery_days
            if intent.max_delivery_days is not None
            else heuristic.max_delivery_days,
            keywords=list(dict.fromkeys([*intent.keywords, *heuristic.keywords])),
        )

    def _parse_heuristically(self, query: str) -> ProcurementIntent:
        normalized = query.lower()
        category = self._extract_category(normalized)
        country = self._extract_country(normalized)
        certifications = self._extract_certifications(query)
        max_price = self._extract_price(normalized)
        max_delivery_days = self._extract_delivery_days(normalized)
        keywords = self._extract_keywords(query, category, country, certifications)
        return ProcurementIntent(
            category=category,
            country=country,
            certifications=certifications,
            max_price=max_price,
            max_delivery_days=max_delivery_days,
            keywords=keywords,
        )

    @staticmethod
    def _extract_category(normalized: str) -> Optional[str]:
        for category, aliases in CATEGORY_KEYWORDS.items():
            if any(alias in normalized for alias in aliases):
                return category
        return None

    @staticmethod
    def _extract_country(normalized: str) -> Optional[str]:
        for alias, country in COUNTRY_ALIASES.items():
            if alias in normalized:
                return country
        return None

    @staticmethod
    def _extract_certifications(query: str) -> list[str]:
        matches = re.findall(r"\b(?:IATF\s*16949|ISO\s*\d{4,5}|FSC|IATF(?=认证|证书|标准|要求|必备|必须|需要|审核|审核通过))", query, flags=re.IGNORECASE)
        normalized = []
        for m in matches:
            m = m.upper().replace("  ", " ")
            if m == "IATF":
                m = "IATF 16949"
            normalized.append(m)
        return list(dict.fromkeys(normalized))

    @staticmethod
    def _extract_price(normalized: str) -> Optional[float]:
        patterns = [
            r"(?:under|below|max|maximum|less than|<=|不超过|低于|以内|预算|unter)\s*€?\s*(\d+(?:[.,]\d+)?)",
            r"€\s*(\d+(?:[.,]\d+)?)\s*(?:or less|以内|max)?",
            r"(\d+(?:[.,]\d+)?)\s*(?:eur|euro|€|欧)\s*(?:以内|or less|max|预算)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return float(match.group(1).replace(",", "."))
        return None

    @staticmethod
    def _extract_delivery_days(normalized: str) -> Optional[int]:
        patterns = [
            r"(?:within|under|max|maximum|<=|不超过|以内|unter)\s*(\d+)\s*(?:days?|天|tage)",
            r"(\d+)\s*(?:days?|天|tage)\s*(?:以内|内|delivery|到货|交期|liefer)",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return int(match.group(1))
        if "urgent" in normalized or "紧急" in normalized:
            return 3
        return None

    @staticmethod
    def _extract_keywords(
        query: str, category: Optional[str], country: Optional[str], certifications: list[str]
    ) -> list[str]:
        words = re.findall(r"[\w\u4e00-\u9fffäöüÄÖÜß+-]+", query)
        stop_words = {
            "find",
            "supplier",
            "suppliers",
            "vendor",
            "vendors",
            "in",
            "with",
            "the",
            "a",
            "an",
            "and",
            "or",
            "我要找",
            "供应商",
        }
        keywords = [word for word in words if len(word) > 2 and word.lower() not in stop_words]
        if category:
            keywords.append(category)
        if country:
            keywords.append(country)
        keywords.extend(certifications)
        return list(dict.fromkeys(keywords))[:12]
