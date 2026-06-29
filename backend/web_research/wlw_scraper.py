"""
WLW.de (Wer liefert was) B2B supplier directory scraper — integrated into ProcureAI.

Runs Selenium in a thread pool, searches wlw.de for B2B suppliers,
extracts company profiles (name, products, contact, location, supplier type,
founding year, delivery range), and returns them as standard supplier candidates.

Falls back gracefully: if Selenium/Chrome is unavailable, returns empty list
so the pipeline falls through to DDG-based web research.

Enhancements over desktop reference:
- Kept clean async wrapper + 5-minute cache (production-ready)
- Added supplier_type extraction (Hersteller/Dienstleister/Händler/etc.)
- Added founding_year extraction via regex
- Added delivery_range extraction
- Multi-dimensional scoring aligned with reference logic
- Removed fragile undetected_chromedriver in favor of webdriver_manager (auto version match)
- Removed debug file writes (not needed in production)
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

_SCRAPE_CACHE: dict[str, list[dict]] = {}
_CACHE_TTL = 300  # 5 minutes


async def search_wlw(search_term: str, limit: int = 5, timeout: int = 50) -> list[dict]:
    """Search wlw.de for B2B suppliers and return structured supplier candidates.

    Returns list of dicts with keys: name, website, country, city, description,
    products, capabilities, supplier_type, founding_year, delivery_range,
    matchScore, phone, email, employee_count.
    Returns empty list if Selenium/Chrome is unavailable.
    """
    cache_key = f"{search_term}:{limit}"
    if cache_key in _SCRAPE_CACHE:
        entry = _SCRAPE_CACHE[cache_key]
        if time.time() - entry.get("_ts", 0) < _CACHE_TTL:
            return entry.get("results", [])

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_scrape_wlw_sync, search_term, limit),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(f"WLW scrape timed out after {timeout}s for '{search_term}'")
        results = []
    except Exception as e:
        logger.warning(f"WLW scrape failed: {e}")
        results = []

    _SCRAPE_CACHE[cache_key] = {"_ts": time.time(), "results": results}
    return results


def _scrape_wlw_sync(search_term: str, limit: int) -> list[dict]:
    """Synchronous WLW scrape — runs in thread pool."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        logger.info("Selenium not installed — skipping WLW")
        return []

    driver = None
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)

        wait = WebDriverWait(driver, 10)

        # ── Search ──────────────────────────────────────────────
        search_url = f"https://www.wlw.de/de/suche/{search_term}"
        driver.get(search_url)
        time.sleep(5)

        # Scroll to load lazy content (reference pattern)
        for scroll_y in [1200, 2500]:
            driver.execute_script(f"window.scrollTo(0, {scroll_y});")
            time.sleep(3)

        # Accept cookies
        try:
            cookie_btn = driver.find_element(By.ID, "cookiescript_accept")
            cookie_btn.click()
            time.sleep(2)
        except Exception:
            pass

        # Find company links (filter: /de/firma/ path, exactly 5 segments, no /produkte/)
        company_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/de/firma/']")
        company_urls = []
        for el in company_elements:
            href = el.get_attribute("href")
            if href and href.count('/') == 5 and "/produkte/" not in href:
                if href not in company_urls:
                    company_urls.append(href)

        logger.info(f"WLW search '{search_term}' → {len(company_urls)} companies, processing {limit}")

        # ── Scrape each company ─────────────────────────────────
        candidates = []
        for i, url in enumerate(company_urls[:limit]):
            try:
                driver.get(url)
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
                time.sleep(3)

                # Scroll to bottom to trigger lazy images/text
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                page_text = driver.find_element(By.TAG_NAME, "body").text

                # ── Company name ──
                name = ""
                try:
                    name = driver.find_element(By.TAG_NAME, "h1").text.strip()
                except Exception:
                    pass

                # ── Products (click "Mehr" to expand) ──
                products = []
                try:
                    more_btn = driver.find_element(By.XPATH, "//button[contains(., 'Mehr')]")
                    driver.execute_script("arguments[0].click();", more_btn)
                    time.sleep(2)
                except Exception:
                    pass
                try:
                    product_els = driver.find_elements(By.CSS_SELECTOR, '[data-test="product-name"] h2')
                    products = [p.text.strip() for p in product_els if p.text.strip()]
                except Exception:
                    pass

                # ── Description ──
                description = ""
                try:
                    desc_el = driver.find_element(By.CSS_SELECTOR, '[data-test="company-description-full"]')
                    description = desc_el.text.strip()[:500]
                except Exception:
                    paragraphs = driver.find_elements(By.TAG_NAME, "p")
                    for p in paragraphs:
                        txt = p.text.strip()
                        if len(txt) > 50:
                            description = txt[:500]
                            break

                # ── Phone ──
                phone = ""
                try:
                    phone_btn = driver.find_element(By.CSS_SELECTOR, "[data-test='view-phone-number'] button")
                    driver.execute_script("arguments[0].click();", phone_btn)
                    time.sleep(2)
                    tel = driver.find_element(By.CSS_SELECTOR, 'a[href^="tel:"]')
                    phone = tel.get_attribute("href").replace("tel:", "")
                except Exception:
                    pass

                # ── Contact person ──
                contact_person = ""
                try:
                    contacts = driver.find_elements(By.CSS_SELECTOR, '[data-test="contact-person"] button')
                    for c in contacts:
                        txt = c.text.strip()
                        if txt:
                            contact_person = txt
                            break
                except Exception:
                    pass

                # ── Employee count ──
                employee_count = ""
                emp_match = re.search(r"Mitarbeiter\s+(\d+-\d+|\d+\+)", page_text)
                if emp_match:
                    employee_count = emp_match.group(1)

                # ── Location / country (reference: check known countries) ──
                country = ""
                for c in ["Deutschland", "Österreich", "Schweiz", "Polen", "Frankreich"]:
                    if c in page_text:
                        country = c
                        break
                # City fallback: look for PLZ pattern
                city = ""
                plz_match = re.search(r'\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)\b', page_text)
                if plz_match:
                    city = plz_match.group(2)

                # ── ✨ NEW: Supplier type (Hersteller / Händler / etc.) ──
                supplier_type: list[str] = []
                _supplier_type_map = [
                    "Hersteller", "Dienstleister", "Händler",
                    "Großhändler", "Lieferant", "Importeur", "Exporteur"
                ]
                for t in _supplier_type_map:
                    if t in page_text and t not in supplier_type:
                        supplier_type.append(t)

                # ── ✨ NEW: Founding year ──
                founding_year = None
                year_match = re.search(r'(19\d{2}|20\d{2})', page_text)
                if year_match:
                    y = int(year_match.group(1))
                    if 1800 < y < 2030:
                        founding_year = y

                # ── ✨ NEW: Delivery range ──
                delivery_range = ""
                try:
                    delivery_el = driver.find_element(
                        By.XPATH, "//span[contains(text(),'Liefergebiet')]/following-sibling::span"
                    )
                    delivery_range = delivery_el.text.strip()
                except Exception:
                    pass

                # ── ✨ ENHANCED: Multi-dimensional scoring (aligned with reference) ──
                score = 50  # base: found on WLW B2B directory
                if products:
                    score += 25   # has product listing (strong signal)
                if phone:
                    score += 15   # phone visible (good contact signal)
                if employee_count:
                    score += 10   # has employee count (legitimacy signal)
                if supplier_type:
                    score += 10   # has supplier type classification
                if description and len(description) > 30:
                    score += 5    # has meaningful description
                if country:
                    score += 5    # has country info
                score = min(100, score)

                candidates.append({
                    "id": f"wlw-{abs(hash(url)) % 10_000_000}",
                    "name": name or "WLW Supplier",
                    "website": url,
                    "country": country,
                    "city": city,
                    "description": description,
                    "products": products,
                    "capabilities": products[:5],
                    "supplier_type": supplier_type,
                    "founding_year": founding_year,
                    "delivery_range": delivery_range,
                    "certifications": [],
                    "matchScore": score,
                    "phone": phone,
                    "email": "",
                    "contactPerson": contact_person,
                    "employees": employee_count,
                    "source": "web",
                    "sourceDetail": "wlw",
                    "sourceUrls": [url],
                    "evidenceSnippets": [description[:200]] if description else [],
                    "is_supplier": True,
                })
            except Exception as e:
                logger.warning(f"WLW company scrape error for {url}: {e}")
                continue
            finally:
                time.sleep(random.uniform(1, 2))

        return candidates

    except Exception as e:
        logger.warning(f"WLW scrape error: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
