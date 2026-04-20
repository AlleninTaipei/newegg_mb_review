"""
Dashboard Generator
Reads motherboard_reviews.json and produces a self-contained dashboard.html
"""

import json
import sys
from pathlib import Path

INPUT_FILE  = "motherboard_reviews.json"
OUTPUT_FILE = "dashboard.html"

BRAND_COLORS = {
    "ASRock":  "#e84118",   # red-orange
    "ASUS":    "#00adb5",   # teal
    "MSI":     "#e94560",   # rose-red
    "Gigabyte": "#f5a623",  # amber
}

BRAND_DARK = {
    "ASRock":  "#c0320e",
    "ASUS":    "#007b82",
    "MSI":     "#b02040",
    "Gigabyte": "#c07a00",
}


def load_data(path: str) -> tuple[list[dict], dict]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    products = []
    for brand, brand_obj in raw["brands"].items():
        for p in brand_obj["products"]:
            products.append({
                "brand":       brand,
                "name":        p["name"],
                "socket":      p.get("socket", "Unknown"),
                "chipset":     p.get("chipset", "Unknown"),
                "form":        p.get("form_factor", "ATX"),
                "rating":      p.get("rating", 0),
                "reviews":     p.get("review_count", 0),
                "price":       p.get("price_usd", 0),
                "platform":    p.get("category", "Unknown"),
            })
    return products, raw


def js_literal(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def build_html(products: list[dict], meta: dict) -> str:
    retrieved_date = meta.get("retrieved_date", "")
    source     = meta.get("source", "Newegg")
    brands_list = list(meta["brands"].keys())

    brand_color_map  = js_literal(BRAND_COLORS)
    brand_dark_map   = js_literal(BRAND_DARK)

    # All unique values for filter dropdowns
    chipsets = sorted({p["chipset"] for p in products if p["chipset"] != "Unknown"})
    forms    = sorted({p["form"]    for p in products})

    max_price = max((p["price"] for p in products), default=1000)
    price_ceil = int((max_price // 100 + 1) * 100)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Motherboard Review Dashboard — {source}</title>
  <style>
    :root {{
      --bg:       #0f1117;
      --surface:  #1a1d27;
      --surface2: #22263a;
      --border:   #2e3350;
      --text:     #e8eaf6;
      --muted:    #8892a4;
      --green:    #27ae60;
      --yellow:   #f1c40f;
      --red:      #e74c3c;
      --accent:   #7c83fd;
    }}
    *  {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{
      font-family:'Segoe UI',system-ui,sans-serif;
      background:var(--bg); color:var(--text);
      min-height:100vh; padding:24px;
    }}

    /* ── Header ── */
    header {{
      display:flex; align-items:center; gap:16px; margin-bottom:28px;
      flex-wrap:wrap;
    }}
    .brand-pills {{ display:flex; gap:8px; flex-wrap:wrap; }}
    .brand-pill {{
      font-size:.75rem; font-weight:800; padding:5px 12px;
      border-radius:20px; color:#fff; letter-spacing:.6px;
    }}
    .header-text h1  {{ font-size:1.4rem; font-weight:700; }}
    .header-text .sub {{ font-size:.82rem; color:var(--muted); margin-top:3px; }}

    /* ── KPI grid ── */
    .kpi-grid {{
      display:grid;
      grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
      gap:14px; margin-bottom:28px;
    }}
    .kpi {{
      background:var(--surface); border:1px solid var(--border);
      border-radius:10px; padding:18px 20px;
    }}
    .kpi .label {{ font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.8px; }}
    .kpi .value {{ font-size:1.9rem; font-weight:800; margin-top:6px; }}
    .kpi .value.green  {{ color:var(--green); }}
    .kpi .value.yellow {{ color:var(--yellow); }}
    .kpi .value.accent {{ color:var(--accent); }}

    /* ── Brand stat cards ── */
    .brand-cards {{
      display:grid;
      grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
      gap:14px; margin-bottom:28px;
    }}
    .brand-card {{
      background:var(--surface); border-radius:10px;
      padding:16px 18px; border-left:4px solid #888;
    }}
    .brand-card h4 {{
      font-size:.78rem; font-weight:700; text-transform:uppercase;
      letter-spacing:.7px; margin-bottom:10px;
    }}
    .brand-stat {{ display:flex; justify-content:space-between; font-size:.82rem; margin-top:5px; }}
    .brand-stat .sv {{ font-weight:700; }}

    /* ── Filters ── */
    .filters {{
      display:flex; flex-wrap:wrap; gap:10px;
      margin-bottom:20px; align-items:center;
    }}
    .filters label {{ font-size:.78rem; color:var(--muted); }}
    .filters select, .filters input[type=text] {{
      background:var(--surface); border:1px solid var(--border);
      color:var(--text); padding:6px 10px; border-radius:6px;
      font-size:.83rem; cursor:pointer;
    }}
    .filters input[type=range] {{
      accent-color:var(--accent); width:110px; cursor:pointer;
    }}
    .range-val {{ font-size:.78rem; color:var(--yellow); min-width:70px; }}
    .filters button {{
      background:var(--surface2); border:1px solid var(--border);
      color:var(--muted); padding:6px 14px; border-radius:6px;
      cursor:pointer; font-size:.82rem;
    }}
    .filters button:hover {{ color:var(--text); }}

    /* ── Table ── */
    .table-wrap {{
      background:var(--surface); border:1px solid var(--border);
      border-radius:10px; overflow:auto; margin-bottom:28px;
    }}
    table {{ width:100%; border-collapse:collapse; font-size:.86rem; min-width:720px; }}
    thead th {{
      background:var(--surface2); padding:11px 13px;
      text-align:left; font-size:.72rem; text-transform:uppercase;
      letter-spacing:.7px; color:var(--muted); white-space:nowrap;
    }}
    tbody tr {{ border-top:1px solid var(--border); transition:background .12s; }}
    tbody tr:hover {{ background:var(--surface2); }}
    tbody td {{ padding:10px 13px; vertical-align:middle; }}

    .brand-dot {{
      display:inline-block; width:8px; height:8px;
      border-radius:50%; margin-right:6px; vertical-align:middle;
    }}
    .name-cell {{ font-weight:600; }}
    .badge {{
      display:inline-block; font-size:.68rem; font-weight:700;
      padding:2px 7px; border-radius:20px; margin-left:5px;
    }}
    .badge.amd   {{ background:#ed1c24; color:#fff; }}
    .badge.intel {{ background:#0071c5; color:#fff; }}
    .tag {{
      display:inline-block; font-size:.68rem; padding:2px 8px;
      border-radius:10px; background:var(--surface2);
      border:1px solid var(--border); color:var(--muted);
    }}
    .stars {{ font-size:.93rem; }}
    .rating-num {{ color:var(--muted); font-size:.78rem; margin-left:3px; }}
    .price {{ font-weight:700; color:var(--yellow); }}
    .bar-wrap {{ display:flex; align-items:center; gap:7px; }}
    .bar {{
      height:7px; border-radius:4px;
      background:var(--border); flex:1; overflow:hidden; min-width:60px;
    }}
    .bar-fill {{ height:100%; border-radius:4px; transition:width .3s; }}
    .tally {{ font-size:.78rem; color:var(--muted); min-width:34px; text-align:right; }}

    /* ── Charts row ── */
    .charts-row {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
      gap:20px; margin-bottom:28px;
    }}
    .chart-card {{
      background:var(--surface); border:1px solid var(--border);
      border-radius:10px; padding:20px;
    }}
    .chart-card h3 {{
      font-size:.8rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:.7px; margin-bottom:16px;
    }}
    .hbar-row  {{ display:flex; align-items:center; gap:9px; margin-bottom:9px; font-size:.8rem; }}
    .hbar-label {{ min-width:170px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .hbar-track {{ flex:1; height:11px; background:var(--border); border-radius:6px; overflow:hidden; }}
    .hbar-fill  {{ height:100%; border-radius:6px; }}
    .hbar-val   {{ min-width:34px; text-align:right; color:var(--muted); font-size:.78rem; }}

    .chipset-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }}
    .chipset-item {{
      background:var(--surface2); border:1px solid var(--border);
      border-radius:8px; padding:10px 8px; text-align:center;
    }}
    .ci-name   {{ font-size:.7rem; color:var(--muted); }}
    .ci-rating {{ font-size:1.25rem; font-weight:800; margin:4px 0; }}
    .ci-count  {{ font-size:.68rem; color:var(--muted); }}

    /* ── Picks row ── */
    .picks-row {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
      gap:20px; margin-bottom:28px;
    }}
    .pick-card {{
      background:var(--surface); border:1px solid var(--border);
      border-radius:10px; padding:20px;
    }}
    .pick-card h3 {{
      font-size:.8rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:.7px; margin-bottom:14px;
    }}
    .pick-item {{
      display:flex; justify-content:space-between; align-items:flex-start;
      padding:9px 0; border-top:1px solid var(--border);
    }}
    .pick-item:first-of-type {{ border-top:none; padding-top:0; }}
    .pick-name {{ font-size:.83rem; font-weight:600; max-width:190px; line-height:1.4; }}
    .pick-brand {{ font-size:.7rem; color:var(--muted); }}
    .pick-meta  {{ text-align:right; }}
    .pick-rating {{ font-size:1.05rem; font-weight:800; color:var(--yellow); }}
    .pick-price  {{ font-size:.76rem; color:var(--muted); }}

    footer {{
      text-align:center; color:var(--muted); font-size:.76rem; margin-top:10px;
    }}

    /* empty state */
    .empty {{
      text-align:center; color:var(--muted); padding:40px;
      font-size:.9rem;
    }}

    /* scrollbar */
    ::-webkit-scrollbar {{ width:6px; height:6px; }}
    ::-webkit-scrollbar-track {{ background:var(--bg); }}
    ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:3px; }}
  </style>
</head>
<body>

<!-- Header -->
<header>
  <div class="brand-pills" id="brandPills"></div>
  <div class="header-text">
    <h1>Motherboard Review Dashboard</h1>
    <div class="sub">
      {source} ratings &amp; pricing &bull; Data as of {retrieved_date} &bull; Source: {source}.com
    </div>
  </div>
</header>

<!-- KPI row -->
<div class="kpi-grid" id="kpiGrid"></div>

<!-- Brand stat cards -->
<div class="brand-cards" id="brandCards"></div>

<!-- Filters -->
<div class="filters">
  <label>Brand</label>
  <select id="fBrand">
    <option value="">All Brands</option>
    {"".join(f'<option value="{b}">{b}</option>' for b in brands_list)}
  </select>

  <label>Platform</label>
  <select id="fPlatform">
    <option value="">All</option>
    <option value="AMD">AMD</option>
    <option value="Intel">Intel</option>
  </select>

  <label>Chipset</label>
  <select id="fChipset">
    <option value="">All</option>
    {"".join(f'<option value="{c}">{c}</option>' for c in chipsets)}
  </select>

  <label>Form</label>
  <select id="fForm">
    <option value="">All</option>
    {"".join(f'<option value="{f}">{f}</option>' for f in forms)}
  </select>

  <label>Min Rating</label>
  <input type="range" id="fRating" min="1" max="5" step="0.1" value="1" />
  <span class="range-val" id="ratingVal">1.0+</span>

  <label>Max Price</label>
  <input type="range" id="fPrice" min="50" max="{price_ceil}" step="10" value="{price_ceil}" />
  <span class="range-val" id="priceVal">${price_ceil}</span>

  <label>Sort</label>
  <select id="fSort">
    <option value="rating_desc">Rating ↓</option>
    <option value="rating_asc">Rating ↑</option>
    <option value="price_asc">Price ↑</option>
    <option value="price_desc">Price ↓</option>
    <option value="reviews_desc">Reviews ↓</option>
    <option value="reviews_asc">Reviews ↑</option>
    <option value="value_desc">Value Score ↓</option>
    <option value="value_asc">Value Score ↑</option>
  </select>

  <button onclick="resetFilters()">Reset</button>
  <span id="filterCount" style="font-size:.78rem;color:var(--muted);margin-left:4px;"></span>
</div>

<!-- Table -->
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Brand / Product</th>
        <th>Chipset</th>
        <th>Form</th>
        <th>Rating</th>
        <th>Reviews</th>
        <th>Price</th>
        <th>Value Score</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<!-- Charts -->
<div class="charts-row">
  <div class="chart-card">
    <h3>Top 10 by Review Count</h3>
    <div id="reviewChart"></div>
  </div>
  <div class="chart-card">
    <h3>Avg Rating by Chipset</h3>
    <div class="chipset-grid" id="chipsetChart"></div>
  </div>
  <div class="chart-card">
    <h3>Avg Rating by Brand</h3>
    <div id="brandChart"></div>
  </div>
</div>

<!-- Picks -->
<div class="picks-row">
  <div class="pick-card">
    <h3>Top Rated (min 10 reviews)</h3>
    <div id="topPicks"></div>
  </div>
  <div class="pick-card">
    <h3>Best Value (rating ÷ price × 100)</h3>
    <div id="valuePicks"></div>
  </div>
  <div class="pick-card">
    <h3>Most Reviewed</h3>
    <div id="popularPicks"></div>
  </div>
</div>

<footer>
  Data sourced from {source}.com &bull; ASRock · ASUS · MSI · Gigabyte Motherboards &bull;
  Dashboard generated {retrieved_date}
</footer>

<script>
const RAW = {js_literal(products)};
const BRAND_COLOR = {brand_color_map};
const BRAND_DARK  = {brand_dark_map};
const PRICE_MAX   = {price_ceil};

// ── Helpers ──────────────────────────────────────────────────────────────────
function ratingColor(r) {{
  return r >= 4.5 ? '#27ae60' : r >= 3.5 ? '#f1c40f' : '#e74c3c';
}}
function valueScore(p) {{
  return p.price > 0 ? ((p.rating / p.price) * 100).toFixed(2) : '0.00';
}}
function stars(r) {{
  const full = Math.floor(r), half = (r - full) >= 0.5 ? 1 : 0, empty = 5 - full - half;
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty);
}}
function brandColor(b) {{ return BRAND_COLOR[b] || '#888'; }}
function brandDot(b) {{
  return `<span class="brand-dot" style="background:${{brandColor(b)}}"></span>`;
}}

// ── Brand pills in header ─────────────────────────────────────────────────────
document.getElementById('brandPills').innerHTML =
  Object.keys(BRAND_COLOR).map(b =>
    `<span class="brand-pill" style="background:${{brandColor(b)}}">${{b}}</span>`
  ).join('');

// ── KPIs ──────────────────────────────────────────────────────────────────────
function renderKPIs(data) {{
  if (!data.length) {{ document.getElementById('kpiGrid').innerHTML = ''; return; }}
  const avg    = (data.reduce((s,p)=>s+p.rating,0)/data.length).toFixed(2);
  const total  = data.reduce((s,p)=>s+p.reviews,0);
  const avgP   = (data.reduce((s,p)=>s+p.price,0)/data.length).toFixed(0);
  const top    = data.filter(p=>p.rating>=4.5).length;
  const brands = [...new Set(data.map(p=>p.brand))].length;
  document.getElementById('kpiGrid').innerHTML = `
    <div class="kpi"><div class="label">Showing</div>
      <div class="value accent">${{data.length}}</div></div>
    <div class="kpi"><div class="label">Brands</div>
      <div class="value">${{brands}}</div></div>
    <div class="kpi"><div class="label">Avg Rating</div>
      <div class="value yellow">${{avg}} ★</div></div>
    <div class="kpi"><div class="label">Total Reviews</div>
      <div class="value">${{total.toLocaleString()}}</div></div>
    <div class="kpi"><div class="label">Avg Price</div>
      <div class="value">$${{avgP}}</div></div>
    <div class="kpi"><div class="label">Rated 4.5+</div>
      <div class="value green">${{top}}</div></div>
  `;
}}

// ── Brand cards ───────────────────────────────────────────────────────────────
function renderBrandCards(data) {{
  const map = {{}};
  data.forEach(p => {{
    if (!map[p.brand]) map[p.brand] = {{ sum:0, cnt:0, reviews:0, prices:[] }};
    map[p.brand].sum += p.rating; map[p.brand].cnt++;
    map[p.brand].reviews += p.reviews; map[p.brand].prices.push(p.price);
  }});
  const html = Object.entries(map).map(([b,v]) => {{
    const avg = (v.sum/v.cnt).toFixed(2);
    const avgP = (v.prices.reduce((a,x)=>a+x,0)/v.prices.length).toFixed(0);
    const col = brandColor(b);
    return `<div class="brand-card" style="border-left-color:${{col}}">
      <h4 style="color:${{col}}">${{b}}</h4>
      <div class="brand-stat"><span>Products</span><span class="sv">${{v.cnt}}</span></div>
      <div class="brand-stat"><span>Avg Rating</span>
        <span class="sv" style="color:${{ratingColor(+avg)}}">${{avg}} ★</span></div>
      <div class="brand-stat"><span>Total Reviews</span>
        <span class="sv">${{v.reviews.toLocaleString()}}</span></div>
      <div class="brand-stat"><span>Avg Price</span>
        <span class="sv" style="color:var(--yellow)">$${{avgP}}</span></div>
    </div>`;
  }}).join('');
  document.getElementById('brandCards').innerHTML = html;
}}

// ── Table ─────────────────────────────────────────────────────────────────────
function renderTable(data) {{
  const tbody = document.getElementById('tableBody');
  if (!data.length) {{
    tbody.innerHTML = '<tr><td colspan="8" class="empty">No products match the current filters.</td></tr>';
    return;
  }}
  const maxR = Math.max(...data.map(p=>p.reviews));
  const vsMax = Math.max(...data.map(p=>+valueScore(p)));
  tbody.innerHTML = data.map((p,i) => {{
    const col = ratingColor(p.rating);
    const vs  = valueScore(p);
    return `<tr>
      <td style="color:var(--muted);font-size:.78rem">${{i+1}}</td>
      <td class="name-cell">
        ${{brandDot(p.brand)}}<span style="color:${{brandColor(p.brand)}};font-size:.72rem;font-weight:700;margin-right:5px">${{p.brand}}</span>
        <a href="https://www.newegg.com/p/pl?d=${{encodeURIComponent(p.name)}}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;border-bottom:1px dotted var(--muted)">${{p.name}}</a>
        <span class="badge ${{p.platform.toLowerCase()}}">${{p.platform}}</span>
      </td>
      <td><span class="tag">${{p.chipset}}</span></td>
      <td style="font-size:.8rem;color:var(--muted)">${{p.form}}</td>
      <td>
        <span class="stars" style="color:${{col}}">${{stars(p.rating)}}</span>
        <span class="rating-num">${{p.rating}}</span>
      </td>
      <td>
        <div class="bar-wrap">
          <div class="bar"><div class="bar-fill"
            style="width:${{maxR>0?(p.reviews/maxR*100).toFixed(1):0}}%;background:${{col}}"></div></div>
          <span class="tally">${{p.reviews.toLocaleString()}}</span>
        </div>
      </td>
      <td class="price">$${{p.price.toFixed(2)}}</td>
      <td>
        <div class="bar-wrap">
          <div class="bar"><div class="bar-fill"
            style="width:${{vsMax>0?(+vs/vsMax*100).toFixed(1):0}}%;background:var(--accent)"></div></div>
          <span class="tally">${{vs}}</span>
        </div>
      </td>
    </tr>`;
  }}).join('');
}}

// ── Review chart ──────────────────────────────────────────────────────────────
function renderReviewChart(data) {{
  const top = [...data].sort((a,b)=>b.reviews-a.reviews).slice(0,10);
  const mx  = top[0]?.reviews || 1;
  document.getElementById('reviewChart').innerHTML = top.map(p => `
    <div class="hbar-row">
      <div class="hbar-label" title="${{p.brand}} ${{p.name}}">
        ${{brandDot(p.brand)}}${{p.name.length>22 ? p.name.slice(0,22)+'…' : p.name}}
      </div>
      <div class="hbar-track">
        <div class="hbar-fill" style="width:${{(p.reviews/mx*100).toFixed(1)}}%;background:${{brandColor(p.brand)}}"></div>
      </div>
      <div class="hbar-val">${{p.reviews.toLocaleString()}}</div>
    </div>`).join('') || '<div class="empty">No data</div>';
}}

// ── Chipset chart ─────────────────────────────────────────────────────────────
function renderChipsetChart(data) {{
  const map = {{}};
  data.forEach(p => {{
    if (p.chipset === 'Unknown') return;
    if (!map[p.chipset]) map[p.chipset] = {{ sum:0, cnt:0 }};
    map[p.chipset].sum += p.rating; map[p.chipset].cnt++;
  }});
  const chips = Object.entries(map)
    .map(([k,v]) => ({{ name:k, avg:+(v.sum/v.cnt).toFixed(2), cnt:v.cnt }}))
    .sort((a,b) => b.avg-a.avg).slice(0,9);
  document.getElementById('chipsetChart').innerHTML = chips.map(c =>
    `<div class="chipset-item">
      <div class="ci-name">${{c.name}}</div>
      <div class="ci-rating" style="color:${{ratingColor(c.avg)}}">${{c.avg}}★</div>
      <div class="ci-count">${{c.cnt}} model${{c.cnt>1?'s':''}}</div>
    </div>`).join('') || '<div class="empty">No data</div>';
}}

// ── Brand chart ───────────────────────────────────────────────────────────────
function renderBrandChart(data) {{
  const map = {{}};
  data.forEach(p => {{
    if (!map[p.brand]) map[p.brand] = {{ sum:0, cnt:0 }};
    map[p.brand].sum += p.rating; map[p.brand].cnt++;
  }});
  const entries = Object.entries(map).map(([b,v]) => ({{ b, avg:+(v.sum/v.cnt).toFixed(2) }}))
    .sort((a,c) => c.avg-a.avg);
  const mx = entries[0]?.avg || 5;
  document.getElementById('brandChart').innerHTML = entries.map(e =>
    `<div class="hbar-row">
      <div class="hbar-label">${{brandDot(e.b)}}<strong>${{e.b}}</strong></div>
      <div class="hbar-track">
        <div class="hbar-fill" style="width:${{(e.avg/5*100).toFixed(1)}}%;background:${{brandColor(e.b)}}"></div>
      </div>
      <div class="hbar-val" style="color:${{ratingColor(e.avg)}}">${{e.avg}}★</div>
    </div>`).join('') || '<div class="empty">No data</div>';
}}

// ── Picks ─────────────────────────────────────────────────────────────────────
function renderPicks(full) {{
  const q10 = full.filter(p=>p.reviews>=10);

  const top5 = [...q10].sort((a,b)=>b.rating-a.rating).slice(0,5);
  document.getElementById('topPicks').innerHTML = top5.map(p=>
    `<div class="pick-item">
      <div><div class="pick-name">${{p.name}}</div>
        <div class="pick-brand" style="color:${{brandColor(p.brand)}}">${{p.brand}}</div></div>
      <div class="pick-meta">
        <div class="pick-rating" style="color:${{ratingColor(p.rating)}}">${{p.rating}}★</div>
        <div class="pick-price">$${{p.price.toFixed(2)}}</div>
      </div>
    </div>`).join('') || '<div class="empty">Not enough data</div>';

  const val5 = [...q10].sort((a,b)=>+valueScore(b)-+valueScore(a)).slice(0,5);
  document.getElementById('valuePicks').innerHTML = val5.map(p=>
    `<div class="pick-item">
      <div><div class="pick-name">${{p.name}}</div>
        <div class="pick-brand" style="color:${{brandColor(p.brand)}}">${{p.brand}}</div></div>
      <div class="pick-meta">
        <div class="pick-rating" style="color:var(--accent)">${{valueScore(p)}}</div>
        <div class="pick-price">$${{p.price.toFixed(2)}}</div>
      </div>
    </div>`).join('') || '<div class="empty">Not enough data</div>';

  const pop5 = [...full].sort((a,b)=>b.reviews-a.reviews).slice(0,5);
  document.getElementById('popularPicks').innerHTML = pop5.map(p=>
    `<div class="pick-item">
      <div><div class="pick-name">${{p.name}}</div>
        <div class="pick-brand" style="color:${{brandColor(p.brand)}}">${{p.brand}}</div></div>
      <div class="pick-meta">
        <div class="pick-rating" style="color:var(--text)">${{p.reviews.toLocaleString()}}</div>
        <div class="pick-price">${{p.rating}}★ · $${{p.price.toFixed(2)}}</div>
      </div>
    </div>`).join('') || '<div class="empty">Not enough data</div>';
}}

// ── Filter & sort ─────────────────────────────────────────────────────────────
function getFiltered() {{
  const brand   = document.getElementById('fBrand').value;
  const plat    = document.getElementById('fPlatform').value;
  const chipset = document.getElementById('fChipset').value;
  const form    = document.getElementById('fForm').value;
  const minR    = +document.getElementById('fRating').value;
  const maxP    = +document.getElementById('fPrice').value;
  const sort    = document.getElementById('fSort').value;

  let data = RAW.filter(p =>
    (!brand   || p.brand    === brand)   &&
    (!plat    || p.platform === plat)    &&
    (!chipset || p.chipset  === chipset) &&
    (!form    || p.form     === form)    &&
    p.rating >= minR &&
    p.price  <= maxP
  );

  data.sort((a,b) => {{
    switch(sort) {{
      case 'rating_desc':  return b.rating  - a.rating;
      case 'rating_asc':   return a.rating  - b.rating;
      case 'price_asc':    return a.price   - b.price;
      case 'price_desc':   return b.price   - a.price;
      case 'reviews_desc': return b.reviews - a.reviews;
      case 'reviews_asc':  return a.reviews - b.reviews;
      case 'value_desc':   return +valueScore(b) - +valueScore(a);
      case 'value_asc':    return +valueScore(a) - +valueScore(b);
    }}
    return 0;
  }});
  return data;
}}

function resetFilters() {{
  ['fBrand','fPlatform','fChipset','fForm','fSort'].forEach(id =>
    document.getElementById(id).value = '');
  document.getElementById('fSort').value = 'rating_desc';
  document.getElementById('fRating').value = '1';
  document.getElementById('fPrice').value  = String(PRICE_MAX);
  document.getElementById('ratingVal').textContent = '1.0+';
  document.getElementById('priceVal').textContent  = '$' + PRICE_MAX;
  render();
}}

function render() {{
  const data = getFiltered();
  document.getElementById('filterCount').textContent =
    data.length < RAW.length ? `${{data.length}} / ${{RAW.length}} shown` : '';
  renderKPIs(data);
  renderBrandCards(data);
  renderTable(data);
  renderReviewChart(data);
  renderChipsetChart(data);
  renderBrandChart(data);
  renderPicks(RAW);  // picks always from full dataset
}}

// ── Chipset dropdown — update options based on Brand + Platform selection ─────
function updateChipsetOptions() {{
  const brand = document.getElementById('fBrand').value;
  const plat  = document.getElementById('fPlatform').value;
  const cur   = document.getElementById('fChipset').value;

  const visible = new Set(
    RAW
      .filter(p => (!brand || p.brand === brand) && (!plat || p.platform === plat))
      .map(p => p.chipset)
      .filter(cs => cs !== 'Unknown')
  );

  const sel = document.getElementById('fChipset');
  Array.from(sel.options).forEach(opt => {{
    if (opt.value === '') return;           // keep "All" option
    opt.hidden = !visible.has(opt.value);
  }});

  // If currently-selected chipset is no longer visible, reset it
  if (cur && !visible.has(cur)) sel.value = '';
}}

// ── Wire controls ─────────────────────────────────────────────────────────────
['fBrand','fPlatform','fChipset','fForm','fSort'].forEach(id =>
  document.getElementById(id).addEventListener('change', render));

// Brand / Platform change → also refresh chipset options
['fBrand','fPlatform'].forEach(id =>
  document.getElementById(id).addEventListener('change', updateChipsetOptions));

document.getElementById('fRating').addEventListener('input', function() {{
  document.getElementById('ratingVal').textContent = (+this.value).toFixed(1) + '+';
  render();
}});
document.getElementById('fPrice').addEventListener('input', function() {{
  document.getElementById('priceVal').textContent = '$' + this.value;
  render();
}});

updateChipsetOptions();
render();
</script>
</body>
</html>
"""


def main():
    src = Path(INPUT_FILE)
    if not src.exists():
        print(f"ERROR: {INPUT_FILE} not found. Run scraper.py first.")
        sys.exit(1)

    products, meta = load_data(INPUT_FILE)
    if not products:
        print("ERROR: No products found in JSON.")
        sys.exit(1)

    html = build_html(products, meta)
    Path(OUTPUT_FILE).write_text(html, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} with {len(products)} products")
    brand_counts = {}
    for p in products:
        brand_counts[p["brand"]] = brand_counts.get(p["brand"], 0) + 1
    for b, c in brand_counts.items():
        print(f"  {b}: {c}")


if __name__ == "__main__":
    main()
