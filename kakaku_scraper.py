"""
Kakaku.com Motherboard Scraper
Fetches ASRock, ASUS, MSI, Gigabyte motherboard listings and saves to kakaku_reviews.json

Output format mirrors motherboard_reviews.json (Newegg scraper) except:
  - price field is price_jpy (Japanese Yen) instead of price_usd
  - source is "Kakaku"
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import date

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.5",
}

BASE_URL = "https://kakaku.com/pc/motherboard/itemlist.aspx"

BRANDS = {
    "ASRock":   {"pdf_ma": 586},
    "ASUS":     {"pdf_ma": 10},
    "MSI":      {"pdf_ma": 53},
    "Gigabyte": {"pdf_ma": 32},
}

OUTPUT_FILE = "kakaku_reviews.json"

# Leave empty to collect all; add chipset strings to restrict
FILTER_CHIPSETS: set[str] = {
    # AMD 800 series (AM5 · Ryzen 9000)
    "X870E", "X870", "B850",
    # AMD 600 series (AM5 · Ryzen 7000)
    "X670E", "X670", "B650E", "B650",
    # Intel 800 series (LGA1851 · Arrow Lake)
    "Z890", "B860", "H810",
    # Intel 700 series (LGA1700 · Raptor Lake)
    "Z790", "B760", "H770",
}


# ── Parsing helpers ───────────────────────────────────────────────────────────

def parse_socket(text: str) -> str:
    u = text.upper().replace(" ", "")
    if "AM5"   in u: return "AM5"
    if "AM4"   in u: return "AM4"
    if "AM3+"  in u: return "AM3+"
    if "AM3"   in u: return "AM3"
    if "LGA1851" in u: return "LGA1851"
    if "LGA1700" in u: return "LGA1700"
    if "LGA1200" in u: return "LGA1200"
    if "LGA1151" in u: return "LGA1151"
    if "LGA1150" in u: return "LGA1150"
    return "Unknown"


def parse_chipset(text: str) -> str:
    u = text.upper().replace(" ", "")
    for cs in [
        "X870E", "X870", "X670E", "X670", "X570", "X470", "X370",
        "B850",  "B650E", "B650", "B550", "B450", "B350", "A520",
        "Z890",  "Z790",  "Z690", "Z590", "Z490", "Z390", "Z370",
        "W790",  "W680",
        "B860",  "B760",  "B660", "B560", "B460", "B365", "B360", "B250",
        "H810",  "H770",  "H670", "H610", "H570", "H470", "H410", "H370", "H310",
    ]:
        if cs in u:
            return cs
    return "Unknown"


def parse_form(text: str) -> str:
    u = text.upper().replace(" ", "").replace("-", "")
    if "EATX" in u or "EXTENDEDATX" in u or "EXTENDED" in u: return "E-ATX"
    if "MINIITX" in u:                     return "Mini-ITX"
    if "MICROATX" in u or "MATX" in u:     return "Micro ATX"
    if "ATX" in u:                          return "ATX"
    return text or "Unknown"


def parse_category(socket: str) -> str:
    if socket in ("AM5", "AM4", "AM3+", "AM3"): return "AMD"
    if socket.startswith("LGA"):                 return "Intel"
    return "Unknown"


def get_last_page(soup) -> int:
    pager = soup.find("div", class_="pagenation")
    if not pager:
        return 1
    last_li = pager.find("li", class_="end")
    if last_li:
        a = last_li.find("a")
        if a:
            m = re.search(r"pdf_pg=(\d+)", a.get("href", ""))
            if m:
                return int(m.group(1))
    return 1


# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape_brand(brand: str, pdf_ma: int) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    page = 1

    while True:
        url = f"{BASE_URL}?pdf_ma={pdf_ma}&pdf_pg={page}"
        print(f"  [{brand}] Page {page}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  [{brand}] Request error: {exc}")
            break

        soup = BeautifulSoup(resp.content, "lxml", from_encoding="cp932")
        last_page = get_last_page(soup)

        # The second tbl-compare02 holds the actual product rows
        tables = soup.select("table.tbl-compare02")
        if len(tables) < 2:
            print(f"  [{brand}] Data table not found — stopping.")
            break

        rows = tables[1].select("tr")
        page_count = 0

        for i, tr in enumerate(rows):
            # Each product's name row has td.ckitemLink
            name_td = tr.find("td", class_="ckitemLink")
            if not name_td:
                continue

            name_a = name_td.find("a", class_="ckitanker")
            if not name_a:
                continue

            # Strip the brand <span> from the link text
            brand_span = name_a.find("span")
            if brand_span:
                brand_span.decompose()
            name = name_a.get_text(strip=True)
            if not name:
                continue

            # Data row is always the next tr (i + 1)
            if i + 1 >= len(rows):
                continue
            data_tr = rows[i + 1]

            # ── Price ─────────────────────────────────────────────────────────
            price_td = data_tr.find("td", class_="td-price")
            if not price_td:
                continue
            m = re.search(r"¥([\d,]+)", price_td.get_text())
            if not m:
                continue
            price = float(m.group(1).replace(",", ""))

            # ── Rating & review count ──────────────────────────────────────────
            # Format: "4.38(43件)"  or  "-(0件)"
            rating = None
            review_count = 0
            for td in data_tr.find_all("td"):
                txt = td.get_text(strip=True)
                m2 = re.match(r"([\d.]+)\((\d+)件\)", txt)
                if m2:
                    rating = float(m2.group(1))
                    review_count = int(m2.group(2))
                    break

            if rating is None:
                continue  # skip unrated products

            # ── Specs (fixed column positions in data row) ─────────────────────
            # [0]alignC [1]td-price [2]swrank1 [3]swrank2 [4]rating
            # [5]kuchikomi [6]swdate1 [7]swdate2
            # [8]form  [9]socket  [10]chipset  [11]memory  [12]end
            all_tds = data_tr.find_all("td")
            form_txt    = all_tds[8].get_text(strip=True)  if len(all_tds) > 8  else ""
            socket_txt  = all_tds[9].get_text(strip=True)  if len(all_tds) > 9  else ""
            chipset_txt = all_tds[10].get_text(strip=True) if len(all_tds) > 10 else ""

            socket   = parse_socket(socket_txt)
            chipset  = parse_chipset(chipset_txt)
            form     = parse_form(form_txt)
            category = parse_category(socket)

            # ── Chipset filter ─────────────────────────────────────────────────
            if FILTER_CHIPSETS and chipset not in FILTER_CHIPSETS:
                continue

            # ── Deduplication ──────────────────────────────────────────────────
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            products.append({
                "name":         name,
                "socket":       socket,
                "chipset":      chipset,
                "form_factor":  form,
                "rating":       rating,
                "review_count": review_count,
                "price_jpy":    round(price),
                "category":     category,
            })
            page_count += 1

        print(f"  [{brand}] {page_count} new products this page")

        if page >= last_page:
            break

        page += 1
        time.sleep(1.5)

    return products


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    result = {
        "source":         "Kakaku",
        "retrieved_date": str(date.today()),
        "currency":       "JPY",
        "brands":         {},
    }

    for brand, cfg in BRANDS.items():
        print(f"\n=== Scraping {brand} ===")
        products = scrape_brand(brand, cfg["pdf_ma"])
        result["brands"][brand] = {"brand": brand, "products": products}
        print(f"  → {len(products)} products collected for {brand}")
        time.sleep(2)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    total = sum(len(v["products"]) for v in result["brands"].values())
    print(f"\nSaved {total} products to {OUTPUT_FILE}")
    print(", ".join(f"{b}: {len(result['brands'][b]['products'])}" for b in BRANDS))


if __name__ == "__main__":
    main()
