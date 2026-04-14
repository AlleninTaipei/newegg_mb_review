# MotherboardAgent

A two-step pipeline that scrapes motherboard listings from Newegg and generates a self-contained interactive HTML dashboard.

```
scraper.py  →  motherboard_reviews.json  →  generate_dashboard.py  →  dashboard.html
```

## Features

**Scraper (`scraper.py`)**
- Fetches new (non-refurbished) motherboard listings for ASRock, ASUS, MSI, and Gigabyte
- Sorts results by rating; scrapes up to the configured page limit per brand
- Infers socket (AM5 / AM4 / LGA1851 / LGA1700 …), chipset (X870E / Z890 / B650 …), and form factor (ATX / Micro ATX / Mini-ITX / E-ATX) directly from product names
- Deduplicates entries and outputs a structured `motherboard_reviews.json`

**Dashboard generator (`generate_dashboard.py`)**
- Reads `motherboard_reviews.json` and writes a fully self-contained `dashboard.html` (no external dependencies)
- All product data is embedded as a JavaScript array — open the file directly in any browser

**Dashboard (`dashboard.html`)**
- Brand color-coded header pills (ASRock / ASUS / MSI / Gigabyte)
- KPI row: product count, active brands, avg rating, total reviews, avg price, count of 4.5+ rated boards
- Per-brand stat cards: product count, avg rating, total reviews, avg price
- Filter panel: brand, platform (AMD / Intel), chipset, form factor, min rating slider, max price slider, sort order, reset button
- Sortable product table with brand dot, chipset tag, star rating, review bar, price, value score bar
- Charts: Top 10 by review count · Avg rating by chipset (top 9) · Avg rating by brand
- Pick panels: Top Rated (min 10 reviews) · Best Value (rating ÷ price × 100) · Most Reviewed

## Requirements

Python 3.11+ with:

```
requests
beautifulsoup4
lxml
```

Install dependencies:

```bash
pip install requests beautifulsoup4 lxml
```

## Usage

### 1. Scrape Newegg

```bash
python3 scraper.py
```

Fetches live data from Newegg and overwrites `motherboard_reviews.json`.  
Default page limits: ASRock 3 pages, ASUS / MSI / Gigabyte 5 pages each (~750+ products total).

### 2. Generate the dashboard

```bash
python3 generate_dashboard.py
```

Reads `motherboard_reviews.json` and writes `dashboard.html`.  
Open `dashboard.html` in any browser — no server needed.

### Full refresh (one-liner)

```bash
python3 scraper.py && python3 generate_dashboard.py
```

## Project structure

```
MotherboardAgent/
├── scraper.py               # Newegg scraper → motherboard_reviews.json
├── generate_dashboard.py    # JSON → dashboard.html
├── motherboard_reviews.json # Scraped data (auto-generated)
└── dashboard.html           # Self-contained dashboard (auto-generated)
```

## Data schema (`motherboard_reviews.json`)

```json
{
  "source": "Newegg",
  "retrieved_date": "2026-04-14",
  "brands": {
    "ASRock": {
      "brand": "ASRock",
      "products": [
        {
          "name": "X870E NOVA WIFI AM5",
          "socket": "AM5",
          "chipset": "X870E",
          "form_factor": "ATX",
          "rating": 4.6,
          "review_count": 282,
          "price_usd": 259.99,
          "category": "AMD"
        }
      ]
    }
  }
}
```

## Customization

**Change which brands or how many pages to scrape** — edit `BRANDS` in `scraper.py`:

```python
BRANDS = {
    "ASRock":  {"n_val": 50001944, "max_pages": 3},
    "ASUS":    {"n_val": 50001315, "max_pages": 5},
    "MSI":     {"n_val": 50001312, "max_pages": 5},
    "Gigabyte":{"n_val": 50001314, "max_pages": 5},
}
```

**Change brand accent colors** — edit `BRAND_COLORS` in `generate_dashboard.py`:

```python
BRAND_COLORS = {
    "ASRock":   "#e84118",
    "ASUS":     "#00adb5",
    "MSI":      "#e94560",
    "Gigabyte": "#f5a623",
}
```

## Notes

- The scraper adds a 1.5-second delay between pages and a 2-second delay between brands to avoid overloading Newegg's servers.
- Refurbished, used, and open-box listings are automatically skipped.
- The Newegg brand filter N-values (`n_val`) were discovered from Newegg's filter sidebar JSON and should remain stable, but may need updating if Newegg restructures its catalog.
