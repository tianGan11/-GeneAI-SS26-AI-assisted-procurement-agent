from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import random
import re

class WLWSeleniumScraper:
    def __init__(self, headless=True):

        chrome_options = Options()

        if headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        self.driver = webdriver.Chrome(
            service=Service(
                ChromeDriverManager().install()
            ),
            options=chrome_options
        )

        self.wait = WebDriverWait(
            self.driver,
            10
        )
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        # 模拟真实浏览器特征
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def scrape_search_results(self, search_term, limit=5):
        results = []
        search_url = f"https://www.wlw.de/de/suche/{search_term}"
        print(f"Navigating to search page: {search_url}")
        
        self.driver.get(search_url)


        time.sleep(5)

        self.driver.execute_script(
            "window.scrollTo(0, 1200);"
        )

        time.sleep(5)

        self.driver.execute_script(
            "window.scrollTo(0, 2500);"
        )

        time.sleep(5)

        # 尝试关闭 Cookie 弹窗
        try:

            cookie_btn = self.driver.find_element(
                By.ID,
                "cookiescript_accept"
            )

            cookie_btn.click()

            print("cookie accepted")

            time.sleep(3)

        except Exception as e:

            print(e)
        # 找到所有供应商卡片链接
        company_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/de/firma/']")
        company_urls = []
        for el in company_elements:
            href = el.get_attribute("href")
            # 确保是公司主页链接，不是产品链接
            if href and href.count('/') == 5 and "/produkte/" not in href:
                if href not in company_urls:
                    company_urls.append(href)
        
        print(f"Found {len(company_urls)} potential companies. Processing first {limit}...")

        for i, url in enumerate(company_urls[:limit]):
            print(f"Scraping ({i+1}/{limit}): {url}")
            data = self.scrape_company_details(url)
            if data:
                results.append(data)
            time.sleep(random.uniform(2, 4))
            
        return results

    def scrape_company_details(self, url):

        self.driver.get(url)

        # 等待页面完全加载
        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "h1")
            )
        )

        time.sleep(5)

        # 自动滚到底
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        time.sleep(3)

        data = {
            "url": url,
            "company_name": "N/A",
            "location": "N/A",
            "description": "N/A",

            "matched_products": [],
            "supplier_type": [],

            "contact_person": "N/A",
            "phone": "N/A",

            "founding_year": None,
            "employee_count": None,
            "delivery_range": "N/A",

            "certificate_count": 0,
            "score": 0
        }

        try:

            page_text = self.driver.find_element(
                By.TAG_NAME,
                "body"
            ).text

            # ==================================================
            # 公司名称
            # ==================================================

            try:
                data["company_name"] = self.driver.find_element(
                    By.TAG_NAME,
                    "h1"
                ).text.strip()
                with open(
                        "debug_page.txt",
                        "w",
                        encoding="utf-8"
                ) as f:

                    f.write(
                        self.driver.find_element(
                            By.TAG_NAME,
                            "body"
                        ).text
                    )
            except:
                pass

            # ==================================================
            # 公司简介
            # ==================================================

            try:

                desc_el = self.driver.find_element(
                    By.CSS_SELECTOR,
                    '[data-test="company-description-full"]'
                )

                data["description"] = desc_el.text.strip()

            except:

                try:

                    paragraphs = self.driver.find_elements(
                        By.TAG_NAME,
                        "p"
                    )

                    for p in paragraphs:

                        txt = p.text.strip()

                        if len(txt) > 50:
                            data["description"] = txt
                            break

                except:
                    pass

            # ==================================================
            # 产品
            # ==================================================
            try:
                more_btn = self.driver.find_element(
                    By.XPATH,
                    "//button[contains(., 'Mehr')]"
                )

                self.driver.execute_script(
                    "arguments[0].click();",
                    more_btn
                )

                time.sleep(3)

            except:
                pass
            try:

                product_names = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    '[data-test="product-name"] h2'
                )

                data["matched_products"] = [
                    p.text.strip()
                    for p in product_names
                    if p.text.strip()
                ]

            except Exception as e:
                print("product error:", e)

            # ==================================================
            # 员工人数
            # ==================================================

            try:
                page_text = self.driver.find_element(
                    By.TAG_NAME,
                    "body"
                ).text

                employee_match = re.search(
                    r"Mitarbeiter\s+(\d+\-\d+|\d+\+)",
                    page_text
                )

                if employee_match:
                    data["employee_count"] = employee_match.group(1)

            except:
                pass

            # ==================================================
            # 配送范围
            # ==================================================

            try:
                delivery = self.driver.find_element(
                    By.XPATH,
                    "//span[contains(text(),'Liefergebiet')]/following-sibling::span"
                )
                data["delivery_range"] = delivery.text.strip()
            except:
                pass
            # ==================================================
            # 联系人
            # ==================================================
            try:
                contacts = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    '[data-test="contact-person"] button'
                )

                data["contact_person"] = "N/A"

                for c in contacts:
                    txt = c.text.strip()

                    if txt:
                        data["contact_person"] = txt
                        break

            except:
                data["contact_person"] = "N/A"
            # ==================================================
            # 电话
            # ==================================================
            try:

                phone_btn = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[data-test='view-phone-number'] button"
                )

                self.driver.execute_script(
                    "arguments[0].click();",
                    phone_btn
                )

                time.sleep(2)

                tel = self.driver.find_element(
                    By.CSS_SELECTOR,
                    'a[href^="tel:"]'
                )

                data["phone"] = (
                    tel.get_attribute("href")
                    .replace("tel:", "")
                )

            except Exception as e:

                print("phone error:", e)

            # ==================================================
            # 成立年份
            # ==================================================

            try:

                year_match = re.search(
                    r'(19\d{2}|20\d{2})',
                    page_text
                )

                if year_match:
                    data["founding_year"] = int(
                        year_match.group(1)
                    )

            except:
                pass

            # ==================================================
            # 供应商类型
            # ==================================================

            supplier_types = [
                "Hersteller",
                "Dienstleister",
                "Händler",
                "Großhändler",
                "Lieferant"
            ]

            for t in supplier_types:

                if t in page_text:
                    data["supplier_type"].append(t)

            # ==================================================
            # 国家
            # ==================================================

            countries = [
                "Deutschland",
                "Österreich",
                "Schweiz",
                "Polen",
                "Frankreich"
            ]

            for country in countries:

                if country in page_text:
                    data["location"] = country
                    break

            # ==================================================
            # 简单评分
            # ==================================================

            score = 0

            if data["matched_products"]:
                score += 30

            if data["phone"] != "N/A":
                score += 20

            if data["employee_count"]:
                score += 20

            if len(data["supplier_type"]) > 0:
                score += 20

            if data["description"] != "N/A":
                score += 10

            data["score"] = score

            print("=" * 60)
            print(data["company_name"])
            print("Employees:", data["employee_count"])
            print("Phone:", data["phone"])
            print("Products:", len(data["matched_products"]))
            print("=" * 60)

        except Exception as e:

            print(
                f"Error parsing details for {url}: {e}"
            )

        return data

if __name__ == "__main__":
    scraper = WLWSeleniumScraper(headless=False)
    try:
        print("Starting Selenium scrape for 'autoglas'...")
        results = scraper.scrape_search_results("autoglas", limit=5) #改limit来控制爬具体多少家供应商
        
        with open("suppliers_selenium.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        
        print(f"Scrape complete. Results saved to suppliers_selenium.json")
    finally:

        scraper.driver.quit()
