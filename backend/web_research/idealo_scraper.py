"""
Idealo.de price comparison scraper — integrated into ProcureAI Agent pipeline.

Runs Selenium in a thread pool, searches idealo.de for products,
extracts structured offers (shop, price, delivery, rating), and returns
them as standard quote/comparison candidates.

Falls back gracefully: if Selenium/Chrome is unavailable, returns empty list
so the pipeline falls through to DDG-based search.

Enhancements over desktop reference:
- Kept clean async wrapper + 5-minute cache (production-ready)
- Added auto_scroll() with random intervals for human-like behavior
- Improved search input: more selectors + human-like typing with natural delays
- Removed fragile undetected_chromedriver in favor of webdriver_manager (auto version match)
- Removed debug HTML file writes (not needed in production)
- Removed over-engineered cookie popup iframe handling (not needed in headless)
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Cache to avoid re-scraping the same query within a session
_SCRAPE_CACHE: dict[str, list[dict]] = {}
_CACHE_TTL = 300  # 5 minutes


async def search_idealo(search_term: str, limit: int = 5, timeout: int = 45) -> list[dict]:
    """Search idealo.de for products and return structured offer candidates.

    Returns list of dicts with keys: product, unitPriceEur, unitLabel,
    vendor, platform, sourceUrls, rating, reviews, deliveryLabel.
    Returns empty list if Selenium/Chrome is unavailable.
    """
    cache_key = f"{search_term}:{limit}"
    if cache_key in _SCRAPE_CACHE:
        entry = _SCRAPE_CACHE[cache_key]
        if time.time() - entry.get("_ts", 0) < _CACHE_TTL:
            return entry.get("results", [])

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_scrape_idealo_sync, search_term, limit),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Idealo scrape timed out after {timeout}s for '{search_term}'")
        results = []
    except Exception as e:
        logger.warning(f"Idealo scrape failed: {e}")
        results = []

    _SCRAPE_CACHE[cache_key] = {"_ts": time.time(), "results": results}
    return results


def _scrape_idealo_sync(search_term: str, limit: int) -> list[dict]:
    """Synchronous scrape — runs in thread pool."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
    except ImportError:
        logger.info("Selenium not installed — skipping idealo")
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
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 15)

        # ── 1. Navigate to Idealo homepage ────────────────────────
        driver.get("https://www.idealo.de/")
        time.sleep(random.uniform(2, 3))

        # ── 2. Find search box (multiple selector fallback) ───────
        search_input = None
        for sel in [
            "input#i-search-input",
            "input[name='q']",
            "input[type='search']",
        ]:
            try:
                search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                if search_input:
                    break
            except Exception:
                continue

        if not search_input:
            logger.warning("Idealo: could not find search input")
            return []

        # ── 3. ✨ ENHANCED: Human-like typing with natural delays ──
        for char in search_term[:80]:
            search_input.send_keys(char)
            time.sleep(random.uniform(0.08, 0.25))  # reference uses 0.1-0.3s

        search_input.send_keys(Keys.ENTER)
        time.sleep(random.uniform(3, 5))

        # ── 4. ✨ NEW: Human-like scrolling to trigger lazy load ───
        _auto_scroll(driver)

        # ── 5. Extract product URLs ───────────────────────────────
        product_links = []
        selectors = [
            "a.productCard-link",
            "div.offerList-item-header a",
            "h3.productCard-title a",
            "a[href*='/OffersOfProduct/']",
        ]
        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                url = el.get_attribute("href")
                if url and "/OffersOfProduct/" in url and url not in product_links:
                    product_links.append(url)
                if len(product_links) >= limit:
                    break
            if len(product_links) >= limit:
                break

        logger.info(f"Idealo: '{search_term}' → {len(product_links)} products (limit {limit})")

        # ── 6. Extract individual product offers ──────────────────
        candidates = []
        for i, url in enumerate(product_links):
            try:
                driver.get(url)
                time.sleep(random.uniform(2, 3))
                _auto_scroll(driver)

                # Product name
                product_name = ""
                for sel in ["h1.oopStage-title", "h1 span", "h1"]:
                    try:
                        product_name = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if product_name:
                            break
                    except Exception:
                        continue

                # Offer rows
                rows = []
                for sel in [".productOffers-listItem", ".offerList-item", "div[data-offer-id]"]:
                    rows = driver.find_elements(By.CSS_SELECTOR, sel)
                    if rows:
                        break

                for row in rows[:3]:  # top 3 offers per product
                    try:
                        # Shop name
                        shop = ""
                        try:
                            shop_el = row.find_element(
                                By.CSS_SELECTOR, ".productOffers-listItemOfferShopV2LogoLink"
                            )
                            shop = shop_el.get_attribute("data-shop-name") or ""
                            shop = shop.split(" - ")[0].strip()
                        except Exception:
                            pass

                        # Price
                        price_text = ""
                        price_eur = None
                        try:
                            price_text = row.find_element(
                                By.CSS_SELECTOR, ".productOffers-listItemOfferPrice, .price"
                            ).text.strip()
                            price_eur = _parse_eur(price_text)
                        except Exception:
                            pass

                        # Delivery
                        delivery_text = ""
                        try:
                            delivery_text = row.find_element(
                                By.CSS_SELECTOR, ".productOffers-listItemOfferDeliveryStatusDatesRange"
                            ).text.strip()
                        except Exception:
                            pass

                        # Rating
                        rating = 0.0
                        reviews = 0
                        try:
                            rating_text = row.find_element(
                                By.CSS_SELECTOR, ".productOffers-listItemOfferShopV2Stars b"
                            ).text.strip()
                            rating = float(rating_text.replace(",", ".")) if rating_text else 0.0
                        except Exception:
                            pass
                        try:
                            reviews_text = row.find_element(
                                By.CSS_SELECTOR,
                                ".productOffers-listItemOfferShopV2NORatings--numberOfRatings",
                            ).text.strip()
                            reviews = int(re.sub(r"[^0-9]", "", reviews_text) or "0")
                        except Exception:
                            pass

                        # Shipping cost (may be empty on idealo)
                        shipping = ""
                        try:
                            shipping_el = row.find_element(
                                By.CSS_SELECTOR, ".productOffers-listItemOfferShippingDetails"
                            )
                            shipping = shipping_el.get_attribute("title") or ""
                        except Exception:
                            pass

                        candidates.append({
                            "product": product_name or search_term,
                            "vendor": shop or "Idealo Shop",
                            "platform": "idealo.de",
                            "unitPriceEur": price_eur,
                            "unitLabel": price_text if price_text else (
                                "€ %.2f" % price_eur if price_eur else "需人工核价"
                            ),
                            "shipping": shipping,
                            "deliveryDays": None,
                            "deliveryLabel": delivery_text or "需确认交期",
                            "rating": rating,
                            "reviews": reviews,
                            "sourceUrls": [url],
                            "sourceDetail": "idealo",
                            "evidenceSnippets": [f"[Idealo] {product_name}: {price_text}"],
                            "priceConfidence": "extracted" if price_eur else "unknown",
                            "matchScore": 75 if price_eur else 55,
                            "paymentTerm": "prepayment",
                            "paymentLabel": "需确认付款方式",
                            "deliveryMethod": "需确认配送方式",
                            "source": "web",
                            "category": "web",
                            "description": "",
                        })
                    except Exception:
                        continue

            except Exception:
                continue
            finally:
                time.sleep(random.uniform(1, 2))

        return candidates

    except Exception as e:
        logger.warning(f"Idealo scrape error: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def _auto_scroll(driver) -> None:
    """✨ NEW: Human-like scrolling — simulates a person browsing search results.

    Scrolls 2-4 times with random 400-800px jumps and 0.5-1.2s pauses.
    This triggers lazy-loaded content and reduces bot-detection risk.
    """
    for _ in range(random.randint(2, 4)):
        scroll_amt = random.randint(400, 800)
        driver.execute_script(f"window.scrollBy(0, {scroll_amt});")
        time.sleep(random.uniform(0.5, 1.2))
    time.sleep(1)


def _parse_eur(text: str) -> Optional[float]:
    """Parse Euro price from text like '2,76 €' or '1.234,56 EUR'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\s]", "", text).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) == 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        else:
            cleaned = cleaned.replace(",", "")
    try:
        val = float(cleaned)
        return val if 0.01 < val < 100000 else None
    except ValueError:
        return None
