"""
Danawa Motherboard Scraper
Fetches ASRock, ASUS, MSI, Gigabyte motherboard listings and saves to danawa_reviews.json

Output format mirrors motherboard_reviews.json (Newegg scraper) except:
  - price field is price_krw (Korean Won) instead of price_usd
  - rating/review_count replaced by store_count (number of stores carrying the product)
  - source is "Danawa"

Uses the AJAX endpoint that backs the Danawa listing page JS pagination.
"""

import os
import shutil
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
    "Accept": "text/html, */*; q=0.01",
    "Accept-Language": "ko,en-US;q=0.7,en;q=0.5",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://prod.danawa.com/list/?cate=112751",
    "Origin": "https://prod.danawa.com",
}

AJAX_URL   = "https://prod.danawa.com/list/ajax/getProductList.ajax.php"
CATE_CODE  = "112751"  # 메인보드 (Motherboard) UI category

BRANDS = {
    "ASRock":   4503,
    "ASUS":     2869,
    "MSI":      2904,
    "Gigabyte": 3148,
}

OUTPUT_FILE = "danawa_reviews.json"
PRE_FILE    = "danawa_reviews_pre.json"

# Known Korean distributor/importer suffixes — stripped before deduplication
DISTRIBUTORS = {
    "에즈윈", "대원씨티에스", "피씨디렉트", "제이씨현", "코잇", "STCOM",
    "디앤디컴", "인텍앤컴퍼니", "벤큐코리아", "성우인터내셔널", "파워렉스",
    "에즈텍", "엠씨컴퍼니", "인지스", "대신코퍼레이션", "유통사 없음",
    "영신텍", "글로벌클락", "테크리더", "리드인터내셔날", "신성ST",
}

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

def strip_distributor(name: str) -> str:
    """Remove trailing Korean distributor/importer name from product name."""
    parts = name.split()
    while parts and parts[-1] in DISTRIBUTORS:
        parts.pop()
    return " ".join(parts)


def parse_spec_list(spec_div) -> dict:
    """
    Parse the spec_list div (comma/slash separated Korean spec text).

    Typical format (separated by <em>/</em>):
      AMD(소켓AM5) / AMD B850 / DDR5 / VGA 연결: PCIe5.0 x16 / M-ATX (24.4x24.4cm) / …
      인텔(소켓1851) / 인텔 B860 / DDR5 / …
    """
    if not spec_div:
        return {"socket": "Unknown", "chipset": "Unknown", "form_factor": "Unknown"}

    # Get plain text, join spec segments without <em> delimiters
    segments = []
    for node in spec_div.children:
        if hasattr(node, "name") and node.name == "em":
            continue  # skip "/" separators
        text = node.get_text(strip=True) if hasattr(node, "get_text") else str(node).strip()
        if text and text != "/":
            segments.append(text)

    full = " ".join(segments)

    return {
        "socket":      _parse_socket(full, segments),
        "chipset":     _parse_chipset(full, segments),
        "form_factor": _parse_form(full, segments),
    }


def _parse_socket(full: str, segments: list[str]) -> str:
    u = full.upper().replace(" ", "")
    if "AM5"    in u: return "AM5"
    if "AM4"    in u: return "AM4"
    if "AM3+"   in u: return "AM3+"
    if "AM3"    in u: return "AM3"
    if "1851"   in u: return "LGA1851"
    if "1700"   in u: return "LGA1700"
    if "1200"   in u: return "LGA1200"
    if "1151"   in u: return "LGA1151"
    if "1150"   in u: return "LGA1150"
    return "Unknown"


def _parse_chipset(full: str, segments: list[str]) -> str:
    # Normalise for matching
    u = full.upper().replace(" ", "").replace("인텔", "").replace("AMD", "")
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


def _parse_form(full: str, segments: list[str]) -> str:
    u = full.upper().replace(" ", "").replace("-", "")
    if "EATX"   in u or "EXTENDEDATX" in u: return "E-ATX"
    if "MINIITX" in u or "M-ITX" in u:      return "Mini-ITX"
    if "MICROATX" in u or "MATX" in u:      return "Micro ATX"
    if "ATX"    in u:                        return "ATX"
    return "Unknown"


def parse_category(socket: str) -> str:
    if socket in ("AM5", "AM4", "AM3+", "AM3"): return "AMD"
    if socket.startswith("LGA"):                 return "Intel"
    return "Unknown"


# ── Scraper ───────────────────────────────────────────────────────────────────

def get_last_page(soup) -> int:
    nav = soup.select_one("div.prod_num_nav")
    if not nav:
        return 1
    links = [a for a in nav.find_all("a", class_="num") if a.get_text(strip=True).isdigit()]
    if links:
        return max(int(a.get_text(strip=True)) for a in links)
    return 1


def scrape_brand(brand: str, maker_id: int) -> list[dict]:
    products: list[dict] = []
    seen_names: set[str] = set()
    page = 1

    while True:
        print(f"  [{brand}] Page {page}: maker={maker_id}")

        payload = {
            "page":            str(page),
            "listCategoryCode": "751",
            "categoryCode":    "751",
            "physicsCate1":    "861",
            "physicsCate2":    "875",
            "physicsCate3":    "0",
            "physicsCate4":    "0",
            "viewMethod":      "LIST",
            "sortMethod":      "",
            "listCount":       "30",
            "group":           "11",
            "depth":           "2",
            "searchMaker[]":   str(maker_id),
            "listType":        "priceCompare",
        }

        try:
            resp = requests.post(AJAX_URL, data=payload, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  [{brand}] Request error: {exc}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        last_page = get_last_page(soup)
        items = soup.select("li.prod_item")

        if not items:
            print(f"  [{brand}] No items found — stopping.")
            break

        page_count = 0

        for item in items:
            li_id = item.get("id", "")
            pcode = li_id.replace("adReaderProductItem", "").replace("productItem", "")

            # ── Name ────────────────────────────────────────────────────────
            name_a = item.select_one(".prod_name a")
            if not name_a:
                continue
            raw_name = name_a.get_text(strip=True)
            model_name = strip_distributor(raw_name)
            if not model_name:
                continue

            # ── Price ────────────────────────────────────────────────────────
            price_strong = item.select_one("p.price_sect strong")
            if not price_strong:
                continue
            price_txt = price_strong.get_text(strip=True).replace(",", "")
            if not price_txt.isdigit():
                continue
            price = int(price_txt)
            if price == 0:
                continue

            # ── Store count ──────────────────────────────────────────────────
            chk_sect = item.select_one("p.chk_sect")
            store_count = 0
            if chk_sect:
                m = re.search(r"(\d+)몰", chk_sect.get_text(strip=True))
                if m:
                    store_count = int(m.group(1))

            # ── Specs ────────────────────────────────────────────────────────
            spec_div = item.select_one("div.spec-box[data-simple-description-open-area='Y'] div.spec_list")
            if not spec_div:
                spec_div = item.select_one("div.spec_list")
            specs = parse_spec_list(spec_div)

            socket      = specs["socket"]
            chipset     = specs["chipset"]
            form_factor = specs["form_factor"]
            category    = parse_category(socket)

            # ── Chipset filter ────────────────────────────────────────────────
            if FILTER_CHIPSETS and chipset not in FILTER_CHIPSETS:
                continue

            # ── Deduplication — keep lowest price per model ───────────────────
            key = model_name.lower()
            existing_idx = None
            for idx, p in enumerate(products):
                if p["_key"] == key:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                if price < products[existing_idx]["price_krw"]:
                    products[existing_idx]["price_krw"] = price
                # accumulate store count across distributors
                products[existing_idx]["store_count"] = max(
                    products[existing_idx]["store_count"], store_count
                )
                continue

            seen_names.add(key)
            products.append({
                "_key":        key,
                "name":        model_name,
                "socket":      socket,
                "chipset":     chipset,
                "form_factor": form_factor,
                "price_krw":   price,
                "store_count": store_count,
                "category":    category,
                "pcode":       pcode,
            })
            page_count += 1

        print(f"  [{brand}] {page_count} new products this page  (total so far: {len(products)})")

        if page >= last_page:
            break

        page += 1
        time.sleep(1.5)

    # Strip internal _key before returning
    for p in products:
        p.pop("_key", None)

    return products


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    result = {
        "source":         "Danawa",
        "retrieved_date": str(date.today()),
        "currency":       "KRW",
        "brands":         {},
    }

    for brand, maker_id in BRANDS.items():
        print(f"\n=== Scraping {brand} (maker={maker_id}) ===")
        products = scrape_brand(brand, maker_id)
        result["brands"][brand] = {"brand": brand, "products": products}
        print(f"  → {len(products)} products collected for {brand}")
        time.sleep(2)

    if os.path.exists(OUTPUT_FILE):
        shutil.copy2(OUTPUT_FILE, PRE_FILE)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    total = sum(len(v["products"]) for v in result["brands"].values())
    print(f"\nSaved {total} products to {OUTPUT_FILE}")
    print(", ".join(f"{b}: {len(result['brands'][b]['products'])}" for b in BRANDS))


if __name__ == "__main__":
    main()
