# MotherboardAgent

A multi-region pipeline that scrapes motherboard market data, generates self-contained interactive HTML dashboards, and optionally delivers them by email. Each region runs as an independent set of programs.

| Region | Source | Currency | Metric |
|--------|--------|----------|--------|
| North America | Newegg | USD | Rating / Review count |
| Japan | Kakaku.com | JPY | Review count |
| Korea | Danawa | KRW | Store count (price-comparison listings) |

```
# North America (Newegg)
scraper.py  →  motherboard_reviews.json  →  generate_dashboard.py  →  dashboard.html
                                                                              ↓
                                                                       send_email.py

# Japan (Kakaku)
kakaku_scraper.py  →  kakaku_reviews.json  →  generate_kakaku_dashboard.py  →  kakaku_dashboard.html
                                                                                        ↓
                                                                               kakaku_send_email.py

# Korea (Danawa)
danawa_scraper.py  →  danawa_reviews.json  →  generate_danawa_dashboard.py  →  danawa_dashboard.html
                                                                                        ↓
                                                                               danawa_send_email.py
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

**Email sender (`send_email.py`)**
- Sends `dashboard.html` as an attachment via SMTP (default: Gmail / port 587)
- Email body includes an HTML summary: KPI cards, avg rating per brand, top-rated pick, best-value pick, and ASRock models below 3 ★
- Plain-text fallback included for non-HTML email clients
- Configured entirely through environment variables (see [Environment variables](#environment-variables))

## Requirements

Python 3.11+ with:

```
requests
beautifulsoup4
lxml
python-dotenv  # optional — loads .env automatically
```

Install dependencies:

```bash
pip install requests beautifulsoup4 lxml
pip install python-dotenv   # optional, for .env file support
```

## Usage

### North America — Newegg

#### 1. Scrape Newegg

```bash
python3 scraper.py
```

Fetches live data from Newegg and overwrites `motherboard_reviews.json`.  
Default page limits: ASRock 3 pages, ASUS / MSI / Gigabyte 5 pages each (~750+ products total).

#### 2. Generate the dashboard

```bash
python3 generate_dashboard.py
```

Reads `motherboard_reviews.json` and writes `dashboard.html`.  
Open `dashboard.html` in any browser — no server needed.

#### 3. Send the dashboard by email

```bash
python3 send_email.py
```

Sends `dashboard.html` as an attachment with an HTML summary in the email body.  
Requires environment variables to be set — see [Environment variables](#environment-variables).

#### Full refresh and deliver (one-liner)

```bash
python3 scraper.py && python3 generate_dashboard.py && python3 send_email.py
```

---

### Japan — Kakaku.com

#### 1. Scrape Kakaku

```bash
python3 kakaku_scraper.py
```

Fetches motherboard listings for ASRock, ASUS, MSI, and Gigabyte from Kakaku.com and writes `kakaku_reviews.json`. Metric: review count per product.

#### 2. Generate the dashboard

```bash
python3 generate_kakaku_dashboard.py
```

Reads `kakaku_reviews.json` and writes `kakaku_dashboard.html`.

#### 3. Send the dashboard by email

```bash
python3 kakaku_send_email.py
```

#### Full refresh and deliver

```bash
python3 kakaku_scraper.py && python3 generate_kakaku_dashboard.py && python3 kakaku_send_email.py
```

---

### Korea — Danawa

Danawa is a price-comparison site; the engagement metric is **store count** (number of stores carrying a product) rather than user ratings.

#### 1. Scrape Danawa

```bash
python3 danawa_scraper.py
```

Fetches motherboard listings for ASRock, ASUS, MSI, and Gigabyte via Danawa's AJAX endpoint and writes `danawa_reviews.json`. Uses `price_krw` and `store_count` fields (no rating/review_count).

#### 2. Generate the dashboard

```bash
python3 generate_danawa_dashboard.py
```

Reads `danawa_reviews.json` and writes `danawa_dashboard.html`.

#### 3. Send the dashboard by email

```bash
python3 danawa_send_email.py
```

#### Full refresh and deliver

```bash
python3 danawa_scraper.py && python3 generate_danawa_dashboard.py && python3 danawa_send_email.py
```

---

### Batch — all regions at once

```bash
bash run_all.sh
```

Runs all three pipelines in parallel. Each region completes its own scrape → dashboard → email sequence independently. The script exits 0 only if all three succeed; any failure is reported with the region name.

## Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAIL_SENDER` | Yes | — | Sending address (e.g. `you@gmail.com`) |
| `EMAIL_PASSWORD` | Yes | — | SMTP password or Gmail App Password |
| `EMAIL_RECIPIENT` | Yes | — | Comma-separated list of recipients |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP port (STARTTLS) |
| `EMAIL_SUBJECT` | No | `Motherboard Dashboard` | Custom subject prefix |

**Gmail setup:** enable 2-Step Verification, then create a 16-character App Password at <https://myaccount.google.com/apppasswords> and set it as `EMAIL_PASSWORD`.

> `.env` is listed in `.gitignore` and will never be committed.

## Project structure

```
MotherboardAgent/
├── scraper.py                    # Newegg scraper → motherboard_reviews.json
├── generate_dashboard.py         # JSON → dashboard.html
├── send_email.py                 # Sends dashboard.html via SMTP
│
├── kakaku_scraper.py             # Kakaku scraper → kakaku_reviews.json
├── generate_kakaku_dashboard.py  # JSON → kakaku_dashboard.html
├── kakaku_send_email.py          # Sends kakaku_dashboard.html via SMTP
│
├── danawa_scraper.py             # Danawa scraper → danawa_reviews.json
├── generate_danawa_dashboard.py  # JSON → danawa_dashboard.html
├── danawa_send_email.py          # Sends danawa_dashboard.html via SMTP
│
├── .env.example             # Environment variable template
├── .env                     # Your credentials (git-ignored)
├── motherboard_reviews.json # Newegg data (auto-generated)
├── kakaku_reviews.json      # Kakaku data (auto-generated)
├── danawa_reviews.json      # Danawa data (auto-generated)
├── dashboard.html           # Newegg dashboard (auto-generated)
├── kakaku_dashboard.html    # Kakaku dashboard (auto-generated)
└── danawa_dashboard.html    # Danawa dashboard (auto-generated)
```

## Data schemas

**`motherboard_reviews.json` (Newegg)**
```json
{
  "source": "Newegg",
  "retrieved_date": "2026-04-14",
  "currency": "USD",
  "brands": {
    "ASRock": {
      "brand": "ASRock",
      "products": [
        { "name": "X870E NOVA WIFI", "socket": "AM5", "chipset": "X870E",
          "form_factor": "ATX", "rating": 4.6, "review_count": 282,
          "price_usd": 259.99, "category": "AMD" }
      ]
    }
  }
}
```

**`kakaku_reviews.json` (Kakaku)**
```json
{
  "source": "Kakaku",
  "retrieved_date": "2026-04-14",
  "currency": "JPY",
  "brands": {
    "ASRock": {
      "brand": "ASRock",
      "products": [
        { "name": "X870E Nova WiFi", "socket": "AM5", "chipset": "X870E",
          "form_factor": "ATX", "review_count": 12,
          "price_jpy": 49800, "category": "AMD" }
      ]
    }
  }
}
```

**`danawa_reviews.json` (Danawa)**
```json
{
  "source": "Danawa",
  "retrieved_date": "2026-04-14",
  "currency": "KRW",
  "brands": {
    "ASRock": {
      "brand": "ASRock",
      "products": [
        { "name": "X870E Nova WiFi", "socket": "AM5", "chipset": "X870E",
          "form_factor": "ATX", "store_count": 45,
          "price_krw": 389000, "category": "AMD" }
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
