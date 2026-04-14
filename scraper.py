"""
Newegg Motherboard Scraper
Fetches ASRock, ASUS, Gigabyte, MSI motherboard listings and saves to motherboard_reviews.json
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
    "Accept-Language": "en-US,en;q=0.5",
}

# Newegg N-values (discovered from filter sidebar JSON)
# 100006654 = general "Motherboard" category (AMD + Intel)
# 100007627 = "Intel Motherboards" only — do NOT use this
MOTHERBOARD_N = 100006654
BRANDS = {
    "ASRock":  {"n_val": 50001944, "max_pages": 3},
    "ASUS":    {"n_val": 50001315, "max_pages": 5},
    "MSI":     {"n_val": 50001312, "max_pages": 5},
    "Gigabyte":{"n_val": 50001314, "max_pages": 5},
}

OUTPUT_FILE = "motherboard_reviews.json"

# ── Scope filters ─────────────────────────────────────────────────────────────
# Leave as empty set() to collect everything; add values to restrict.
# Examples:
#   FILTER_SOCKETS  = {"AM5"}
#   FILTER_CHIPSETS = {"X870E", "X870", "B850", "B650"}
FILTER_SOCKETS:  set[str] = set()
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

def parse_socket(name: str) -> str:
    u = name.upper()
    if "AM5" in u:              return "AM5"
    if "AM4" in u:              return "AM4"
    if "AM3+" in u:             return "AM3+"
    if "AM3" in u:              return "AM3"
    if "LGA 1851" in u or "LGA1851" in u: return "LGA1851"
    if "LGA 1700" in u or "LGA1700" in u: return "LGA1700"
    if "LGA 1200" in u or "LGA1200" in u: return "LGA1200"
    if "LGA 1151" in u or "LGA1151" in u: return "LGA1151"
    if "LGA 1150" in u or "LGA1150" in u: return "LGA1150"
    if "LGA 2066" in u or "LGA2066" in u: return "LGA2066"
    if "LGA 2011" in u or "LGA2011" in u: return "LGA2011"
    if "LGA 4677" in u or "LGA4677" in u: return "LGA4677"
    if "LGA 1155" in u or "LGA1155" in u: return "LGA1155"
    if re.search(r"\bN\d{3}\b", u):       return "Integrated"
    return "Unknown"


def parse_chipset(name: str) -> str:
    u = name.upper()
    # Ordered: more specific first
    for cs in [
        "X870E", "X870", "X670E", "X670", "X570", "X470", "X370",
        "B850",  "B650E","B650",  "B550", "B450", "B350", "A520",
        "Z890",  "Z790", "Z690",  "Z590", "Z490", "Z390", "Z370", "Z270", "Z170",
        "W790",  "W680",
        "B860",  "B760", "B660",  "B560", "B460", "B365", "B360", "B250",
        "H810",  "H770", "H670",  "H570", "H470", "H410", "H370", "H310",
        "H270",  "H170", "H110",
        "N100",  "N305", "N97",   "J6412",
        "X299",  "X399", "TRX40", "TRX50",
    ]:
        if cs in u:
            return cs
    return "Unknown"


def parse_form(name: str) -> str:
    u = name.upper()
    if "EXTENDED ATX" in u or "E-ATX" in u or "EATX" in u:
        return "E-ATX"
    if "MINI-ITX" in u or "MINI ITX" in u or "MINIITX" in u:
        return "Mini-ITX"
    if re.search(r"[-\s]ITX\b", u):
        return "Mini-ITX"
    if "MICRO ATX" in u or "MICRO-ATX" in u or "MATX" in u or "M-ATX" in u:
        return "Micro ATX"
    if re.search(r"\bMICROATX\b", u):
        return "Micro ATX"
    return "ATX"


def parse_category(socket: str) -> str:
    if socket in ("AM5", "AM4", "AM3+", "AM3"):
        return "AMD"
    if socket.startswith("LGA") or socket == "Integrated":
        return "Intel"
    return "Unknown"


def parse_price(item) -> float | None:
    strong = item.select_one(".price-current strong")
    sup    = item.select_one(".price-current sup")
    if strong:
        try:
            dollars = strong.get_text(strip=True).replace(",", "")
            cents   = sup.get_text(strip=True).lstrip(".") if sup else "00"
            return float(f"{dollars}.{cents}")
        except ValueError:
            pass
    return None


def parse_rating(item) -> float | None:
    el = item.select_one(".item-rating i")
    if el:
        m = re.search(r"rated ([\d.]+) out of", el.get("aria-label", ""))
        if m:
            return float(m.group(1))
        # Fallback via CSS class: 'rating-4-5' → 4.5, 'rating-5' → 5.0
        for cls in el.get("class", []):
            m2 = re.match(r"rating-(\d+)-(\d+)$", cls)
            if m2:
                return float(f"{m2.group(1)}.{m2.group(2)}")
            m3 = re.match(r"rating-(\d+)$", cls)
            if m3:
                return float(m3.group(1))
    return None


def parse_review_count(item) -> int:
    el = item.select_one(".item-rating-num")
    if el:
        m = re.search(r"\((\d+)\)", el.get_text())
        if m:
            return int(m.group(1))
    return 0


# ── Scraper ───────────────────────────────────────────────────────────────────

SKIP_KEYWORDS = ("Refurbished", "Used -", "Open Box", "Like New", "Renewed")


def scrape_brand(brand: str, n_val: int, max_pages: int) -> list[dict]:
    products = []
    seen_names: set[str] = set()

    for page in range(1, max_pages + 1):
        url = (
            f"https://www.newegg.com/p/pl"
            f"?N={MOTHERBOARD_N}+{n_val}&PageSize=96&Order=RATING&Page={page}"
        )
        print(f"  [{brand}] Page {page}: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  [{brand}] Request error: {exc}")
            break

        soup  = BeautifulSoup(resp.text, "lxml")
        items = soup.select(".item-container")
        if not items:
            print(f"  [{brand}] No items found – stopping.")
            break

        page_scraped = 0
        for item in items:
            title_el = item.select_one(".item-title")
            if not title_el:
                continue

            # Strip the open-box italic span from title text
            for span in title_el.select(".item-open-box-italic"):
                span.decompose()
            title = title_el.get_text(strip=True)

            # Skip non-new listings
            if any(kw in title for kw in SKIP_KEYWORDS):
                continue

            price  = parse_price(item)
            rating = parse_rating(item)
            if price is None or rating is None:
                continue

            reviews  = parse_review_count(item)
            socket   = parse_socket(title)
            chipset  = parse_chipset(title)

            # Apply scope filters (empty set = no restriction)
            if FILTER_SOCKETS  and socket  not in FILTER_SOCKETS:  continue
            if FILTER_CHIPSETS and chipset not in FILTER_CHIPSETS: continue

            form     = parse_form(title)
            category = parse_category(socket)

            # Remove brand prefix for the stored name
            model = title
            for prefix in (f"{brand} ", brand):
                if model.upper().startswith(prefix.upper()):
                    model = model[len(prefix):].strip()
                    break

            # Deduplicate
            key = model.lower()
            if key in seen_names:
                continue
            seen_names.add(key)

            products.append({
                "name":         model,
                "socket":       socket,
                "chipset":      chipset,
                "form_factor":  form,
                "rating":       rating,
                "review_count": reviews,
                "price_usd":    round(price, 2),
                "category":     category,
            })
            page_scraped += 1

        print(f"  [{brand}] Scraped {page_scraped} new products this page")

        # Stop when we've reached the last page
        page_info_el = soup.select_one(".list-tool-pagination-text strong")
        if page_info_el:
            m = re.match(r"(\d+)/(\d+)", page_info_el.get_text())
            if m and int(m.group(1)) >= int(m.group(2)):
                break

        time.sleep(1.5)   # be polite to Newegg

    return products


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    result = {
        "source":         "Newegg",
        "retrieved_date": str(date.today()),
        "brands":         {},
    }

    for brand, cfg in BRANDS.items():
        print(f"\n=== Scraping {brand} ===")
        products = scrape_brand(brand, cfg["n_val"], cfg["max_pages"])
        result["brands"][brand] = {"brand": brand, "products": products}
        print(f"  → {len(products)} products collected for {brand}")
        time.sleep(2)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    total = sum(len(v["products"]) for v in result["brands"].values())
    print(f"\nSaved {total} products to {OUTPUT_FILE}")
    brand_summary = ", ".join(f"{b}: {len(result['brands'][b]['products'])}" for b in BRANDS)
    print(f"Brands: {brand_summary}")


if __name__ == "__main__":
    main()
