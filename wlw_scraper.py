import requests
from bs4 import BeautifulSoup
import json
import time
import random

class WLWScraper:
    def __init__(self):
        self.base_url = "https://www.wlw.de"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def get_soup(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def scrape_search_results(self, search_term, max_pages=1):
        results = []
        search_url = f"{self.base_url}/de/suche/{search_term}"
        
        soup = self.get_soup(search_url)
        if not soup:
            return results

        # 查找供应商列表
        # 这里的 class 可能会变化，我们使用更通用的方式
        # 供应商链接通常包含 /de/firma/
        company_links = soup.find_all('a', href=lambda x: x and '/de/firma/' in x and x.count('/') == 3)
        
        seen_urls = set()
        for link in company_links:
            href = link.get('href')
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            company_url = self.base_url + href
            print(f"Scraping details for: {company_url}")
            details = self.scrape_company_details(company_url)
            if details:
                results.append(details)
            
            # 礼貌爬取
            time.sleep(random.uniform(1, 2))
            
        return results

    def scrape_company_details(self, url):
        soup = self.get_soup(url)
        if not soup:
            return None

        data = {
            "url": url,
            "company_name": "",
            "location": "",
            "description": "",
            "matched_products": [],
            "supplier_type": [],
            "founding_year": None,
            "employee_count": None,
            "delivery_range": "",
            "certificate_count": 0,
            "score": 0
        }

        # 公司名
        h1 = soup.find('h1')
        if h1:
            data["company_name"] = h1.get_text(strip=True)

        # 地区 - 查找包含地址信息的 div
        location_tag = soup.find('div', class_=lambda x: x and 'location' in x.lower()) or \
                       soup.find('address')
        if not location_tag:
            # 尝试查找包含国名的 div，通常在 h1 下方
            potential_locations = soup.find_all('div', string=lambda x: x and any(country in x for country in ['Deutschland', 'Österreich', 'Schweiz']))
            if potential_locations:
                data["location"] = potential_locations[0].get_text(strip=True)
        else:
            data["location"] = location_tag.get_text(strip=True)

        # 简介
        desc_tag = soup.find('div', class_=lambda x: x and 'description' in x.lower()) or \
                   soup.find('div', id='company-description') or \
                   soup.find('p', class_=lambda x: x and 'text-neutral-80' in x)
        if desc_tag:
            data["description"] = desc_tag.get_text(strip=True)

        # 匹配产品
        products = soup.find_all('a', href=lambda x: x and '/produkte/' in x)
        data["matched_products"] = list(set([p.get_text(strip=True) for p in products if p.get_text(strip=True)]))

        # 供应商类型
        # 在 wlw 上，类型通常是图标旁边的文字：Hersteller, Dienstleister, Händler
        types = ["Hersteller", "Dienstleister", "Händler", "Großhändler", "Lieferant"]
        for t in types:
            if soup.find(string=lambda x: x and t in x):
                data["supplier_type"].append(t)

        # 成立年份、员工数、配送范围
        # wlw 详情页的信息通常在图标下方的文本中
        # 我们查找包含特定文本的 div
        info_divs = soup.find_all('div', class_=lambda x: x and 'flex' in x)
        for div in info_divs:
            text = div.get_text(strip=True)
            if 'Gegründet' in text or (div.find('img') and 'founding' in str(div.find('img'))):
                import re
                years = re.findall(r'\b(19|20)\d{2}\b', text)
                if not years: # 尝试找紧随其后的 div
                    next_div = div.find_next_sibling('div')
                    if next_div:
                        years = re.findall(r'\b(19|20)\d{2}\b', next_div.get_text())
                if years:
                    data["founding_year"] = int(years[0])
            
            if 'Mitarbeiter' in text or (div.find('img') and 'employee' in str(div.find('img'))):
                import re
                matches = re.findall(r'\d+-\d+|\d+\+', text)
                if not matches:
                    next_div = div.find_next_sibling('div')
                    if next_div:
                        matches = re.findall(r'\d+-\d+|\d+\+', next_div.get_text())
                if matches:
                    data["employee_count"] = matches[0]
            
            if 'Liefergebiet' in text or (div.find('img') and 'distribution' in str(div.find('img'))):
                val = text.replace('Liefergebiet:', '').strip()
                if not val:
                    next_div = div.find_next_sibling('div')
                    if next_div:
                        val = next_div.get_text(strip=True)
                data["delivery_range"] = val

        # 证书数
        certs = soup.find_all(string=lambda x: x and 'Zertifikat' in x)
        data["certificate_count"] = len(certs)

        # 评分逻辑 (简单打分)
        data["score"] = self.calculate_score(data)

        return data

    def calculate_score(self, data):
        score = 0
        # 1. 供应商类型 (制造商权重最高)
        if "Hersteller" in data["supplier_type"]:
            score += 40
        elif "Dienstleister" in data["supplier_type"]:
            score += 20
        
        # 2. 成立年份 (历史悠久加分)
        if data["founding_year"]:
            years_active = 2024 - data["founding_year"]
            if years_active > 20:
                score += 20
            elif years_active > 10:
                score += 10
        
        # 3. 证书数
        if data["certificate_count"] > 0:
            score += min(data["certificate_count"] * 5, 20)
            
        # 4. 配送范围 (国际/全国加分)
        if "International" in data["delivery_range"] or "Europa" in data["delivery_range"]:
            score += 20
        elif "National" in data["delivery_range"]:
            score += 10
            
        return score

if __name__ == "__main__":
    scraper = WLWScraper()
    print("Starting scrape for 'autoglas'...")
    results = scraper.scrape_search_results("autoglas", max_pages=1)
    
    output_file = "suppliers_autoglas.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"Scraping complete. Found {len(results)} suppliers. Results saved to {output_file}")
