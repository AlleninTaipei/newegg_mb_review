"""
send_email.py
Sends the Motherboard Review Dashboard (dashboard.html) via email.

Configuration — set these environment variables (or create a .env file):
  EMAIL_SENDER       your sending address, e.g. you@gmail.com
  EMAIL_PASSWORD     app-password / SMTP password
  EMAIL_RECIPIENT    comma-separated list of recipients
  SMTP_HOST          (optional) default: smtp.gmail.com
  SMTP_PORT          (optional) default: 587
  EMAIL_SUBJECT      (optional) custom subject line

Quick start with Gmail:
  1. Enable 2-Step Verification on your Google account.
  2. Create an App Password at https://myaccount.google.com/apppasswords
  3. Set EMAIL_PASSWORD to that 16-char app password.
"""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

# ── optional python-dotenv support ────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — use real env vars


# ── configuration ─────────────────────────────────────────────────────────────
SENDER     = os.environ.get("EMAIL_SENDER", "")
PASSWORD   = os.environ.get("EMAIL_PASSWORD", "")
RECIPIENT  = os.environ.get("EMAIL_RECIPIENT", "")
SMTP_HOST  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587"))

DASHBOARD_FILE = Path("dashboard.html")
DATA_FILE      = Path("motherboard_reviews.json")


# ── helpers ───────────────────────────────────────────────────────────────────
def load_summary() -> dict:
    """Parse motherboard_reviews.json and return key stats."""
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)

    products = []
    for brand, brand_obj in raw["brands"].items():
        for p in brand_obj["products"]:
            products.append({**p, "brand": brand})

    if not products:
        return {}

    total_reviews = sum(p.get("review_count", 0) for p in products)

    top_rated = max(
        (p for p in products if p.get("review_count", 0) >= 10),
        key=lambda p: p["rating"],
        default=None,
    )

    best_value = max(
        (p for p in products if p.get("price_usd", 0) > 0),
        key=lambda p: p["rating"] / p["price_usd"] * 100,
        default=None,
    )

    asrock_low = sorted(
        [p for p in products if p["brand"] == "ASRock" and p["rating"] < 3],
        key=lambda p: p["rating"],
    )

    brand_avgs = {}
    for brand, brand_obj in raw["brands"].items():
        ps = brand_obj["products"]
        if ps:
            brand_avgs[brand] = sum(p["rating"] for p in ps) / len(ps)

    return {
        "source": raw.get("source", "Newegg"),
        "retrieved_date": raw.get("retrieved_date", ""),
        "total_products": len(products),
        "brands": list(raw["brands"].keys()),
        "total_reviews": total_reviews,
        "top_rated": top_rated,
        "best_value": best_value,
        "asrock_low": asrock_low,
        "brand_avgs": brand_avgs,
    }


def build_html_body(s: dict) -> str:
    """Build a compact HTML summary for the email body."""
    if not s:
        return "<p>Dashboard data unavailable.</p>"

    brand_rows = "".join(
        f"<tr><td>{b}</td><td style='text-align:right'>{avg:.2f} ★</td></tr>"
        for b, avg in sorted(s["brand_avgs"].items(), key=lambda x: -x[1])
    )

    # 1. Top Rated (min 10 reviews)
    if s.get("top_rated"):
        p = s["top_rated"]
        top_html = f"""
        <div class="pick-name">{p['name']}</div>
        <div class="pick-meta">
          <span class="hl">{p['rating']} ★</span>
          &nbsp;·&nbsp; {p.get('review_count', 0):,} reviews
          &nbsp;·&nbsp; ${p.get('price_usd', 0):.2f}
        </div>"""
    else:
        top_html = "<div class='pick-meta'>—</div>"

    # 2. Best Value (rating / price * 100)
    if s.get("best_value"):
        p = s["best_value"]
        score = p["rating"] / p["price_usd"] * 100
        bv_html = f"""
        <div class="pick-name">{p['name']}</div>
        <div class="pick-meta">
          Score <span class="hl">{score:.2f}</span>
          &nbsp;·&nbsp; {p['rating']} ★
          &nbsp;·&nbsp; ${p.get('price_usd', 0):.2f}
        </div>"""
    else:
        bv_html = "<div class='pick-meta'>—</div>"

    # 3. ASRock models under rating 3
    asrock_low = s.get("asrock_low", [])
    if asrock_low:
        asrock_rows = "".join(
            f"<tr><td>{p['name']}</td>"
            f"<td style='text-align:right;color:#e74c3c;font-weight:700'>{p['rating']} ★</td></tr>"
            for p in asrock_low
        )
        asrock_html = f"<table><thead><tr><th>Model</th><th style='text-align:right'>Rating</th></tr></thead><tbody>{asrock_rows}</tbody></table>"
    else:
        asrock_html = "<p style='color:#636e72;font-size:.82rem'>No ASRock models below 3 ★.</p>"

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body      {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f5f6fa; margin:0; padding:20px; color:#2d3436; }}
  .card     {{ background:#fff; border-radius:10px; padding:24px 28px; max-width:640px;
               margin:0 auto; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
  h2        {{ margin:0 0 4px; font-size:1.2rem; color:#2d3436; }}
  .sub      {{ color:#636e72; font-size:.82rem; margin-bottom:20px; }}
  .kpis     {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
  .kpi      {{ flex:1; min-width:110px; background:#f0f3ff; border-radius:8px; padding:12px 14px; }}
  .kl       {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.6px; color:#636e72; }}
  .kv       {{ font-size:1.4rem; font-weight:800; color:#2d3436; margin-top:3px; }}
  table     {{ width:100%; border-collapse:collapse; font-size:.83rem; margin-bottom:0; }}
  th        {{ text-align:left; color:#636e72; font-size:.72rem; text-transform:uppercase;
               padding:6px 8px; border-bottom:1px solid #dfe6e9; }}
  td        {{ padding:7px 8px; border-bottom:1px solid #f0f3ff; }}
  .label    {{ background:#6c5ce7; color:#fff; font-size:.7rem; border-radius:4px;
               padding:2px 7px; display:inline-block; margin-bottom:12px; }}
  .section  {{ margin-bottom:18px; }}
  .sec-title {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.7px;
                color:#636e72; font-weight:700; margin-bottom:8px; }}
  .pick-name {{ font-size:.85rem; font-weight:600; margin-bottom:3px; }}
  .pick-meta {{ font-size:.8rem; color:#636e72; }}
  .footer   {{ font-size:.73rem; color:#b2bec3; text-align:center; margin-top:18px; }}
  .hl       {{ color:#6c5ce7; font-weight:700; }}
  .divider  {{ border:none; border-top:1px solid #f0f3ff; margin:16px 0; }}
  .tip      {{ background:#f0edff; border-left:4px solid #6c5ce7; border-radius:6px;
               padding:12px 16px; margin-top:20px; }}
  .tip-head {{ font-size:.72rem; font-weight:800; text-transform:uppercase;
               letter-spacing:.6px; color:#6c5ce7; margin-bottom:6px; }}
  .tip-row  {{ display:flex; gap:8px; align-items:baseline; margin-top:4px; font-size:.8rem; }}
  .tip-icon {{ font-size:.85rem; }}
  .tip-text {{ color:#2d3436; line-height:1.45; }}
</style>
</head>
<body>
<div class="card">
  <span class="label">{s['source']}</span>
  <h2>Motherboard Review Dashboard</h2>
  <div class="sub">Data as of {s['retrieved_date']} &bull; {', '.join(s['brands'])}</div>

  <div class="kpis">
    <div class="kpi"><div class="kl">Products</div>
      <div class="kv">{s['total_products']}</div></div>
    <div class="kpi"><div class="kl">Total Reviews</div>
      <div class="kv">{s['total_reviews']:,}</div></div>
    <div class="kpi"><div class="kl">Brands</div>
      <div class="kv">{len(s['brands'])}</div></div>
    <div class="kpi"><div class="kl">ASRock &lt;3★</div>
      <div class="kv" style="color:#e74c3c">{len(asrock_low)}</div></div>
  </div>

  <div class="section">
    <table>
      <thead><tr><th>Brand</th><th style="text-align:right">Avg Rating</th></tr></thead>
      <tbody>{brand_rows}</tbody>
    </table>
  </div>

  <hr class="divider">

  <div class="section">
    <div class="sec-title">1. Top Rated (min 10 reviews)</div>
    {top_html}
  </div>

  <hr class="divider">

  <div class="section">
    <div class="sec-title">2. Best Value (rating ÷ price × 100)</div>
    {bv_html}
  </div>

  <hr class="divider">

  <div class="section">
    <div class="sec-title">3. ASRock models under 3 ★</div>
    {asrock_html}
  </div>

  <div class="tip">
    <div class="tip-head">How to use this report</div>
    <div class="tip-row">
      <span class="tip-icon">📱</span>
      <span class="tip-text"><strong>This email</strong> — a mobile-ready summary for quick review on any device.</span>
    </div>
    <div class="tip-row">
      <span class="tip-icon">🖥️</span>
      <span class="tip-text"><strong>dashboard.html</strong> (attached) — full interactive dashboard with filters, charts, and sortable table. Best opened on a desktop browser.</span>
    </div>
  </div>
</div>
</body>
</html>
"""


def build_text_body(s: dict) -> str:
    """Plain-text fallback."""
    if not s:
        return "Dashboard data unavailable."
    lines = [
        f"Motherboard Review Dashboard — {s['source']}",
        f"Data as of: {s['retrieved_date']}",
        "",
        f"Products      : {s['total_products']}",
        f"Total Reviews : {s['total_reviews']:,}",
        f"Brands        : {', '.join(s['brands'])}",
        "",
        "Avg Rating by Brand:",
    ]
    for b, avg in sorted(s["brand_avgs"].items(), key=lambda x: -x[1]):
        lines.append(f"  {b:<12} {avg:.2f} ★")

    lines.append("")
    lines.append("─" * 50)

    # 1. Top Rated
    lines.append("1. TOP RATED (MIN 10 REVIEWS)")
    if s.get("top_rated"):
        p = s["top_rated"]
        lines.append(f"   {p['name']}")
        lines.append(f"   {p['rating']} ★  ·  {p.get('review_count', 0):,} reviews  ·  ${p.get('price_usd', 0):.2f}")
    else:
        lines.append("   —")

    lines.append("")
    lines.append("─" * 50)

    # 2. Best Value
    lines.append("2. BEST VALUE (RATING / PRICE × 100)")
    if s.get("best_value"):
        p = s["best_value"]
        score = p["rating"] / p["price_usd"] * 100
        lines.append(f"   {p['name']}")
        lines.append(f"   Score {score:.2f}  ·  {p['rating']} ★  ·  ${p.get('price_usd', 0):.2f}")
    else:
        lines.append("   —")

    lines.append("")
    lines.append("─" * 50)

    # 3. ASRock under 3
    asrock_low = s.get("asrock_low", [])
    lines.append("3. ASROCK MODELS UNDER RATING 3")
    if asrock_low:
        for p in asrock_low:
            lines.append(f"   {p['rating']} ★  {p['name']}")
    else:
        lines.append("   No ASRock models below 3 ★.")

    lines += ["", "Full interactive dashboard attached — open dashboard.html in a browser."]
    return "\n".join(lines)


def send(subject: str | None = None) -> None:
    # ── validate config ────────────────────────────────────────────────────────
    missing = [v for v in ("EMAIL_SENDER", "EMAIL_PASSWORD", "EMAIL_RECIPIENT") if not os.environ.get(v)]
    if missing:
        print("ERROR: Missing environment variables:", ", ".join(missing))
        print(__doc__)
        sys.exit(1)

    if not DASHBOARD_FILE.exists():
        print(f"ERROR: {DASHBOARD_FILE} not found. Run generate_dashboard.py first.")
        sys.exit(1)

    recipients = [r.strip() for r in RECIPIENT.split(",") if r.strip()]
    summary    = load_summary()
    date_tag   = summary.get("retrieved_date") or datetime.today().strftime("%Y-%m-%d")
    subject    = (subject or os.environ.get("EMAIL_SUBJECT") or "[Newegg] Motherboard Dashboard") + f" [{date_tag}]"

    # ── assemble message ───────────────────────────────────────────────────────
    msg = MIMEMultipart("mixed")
    msg["From"]    = SENDER
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject

    # alternative part: text + html
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(build_text_body(summary), "plain", "utf-8"))
    alt.attach(MIMEText(build_html_body(summary), "html",  "utf-8"))
    msg.attach(alt)

    # attachment: full dashboard
    html_bytes = DASHBOARD_FILE.read_bytes()
    attachment = MIMEApplication(html_bytes, Name="dashboard.html")
    attachment["Content-Disposition"] = 'attachment; filename="dashboard.html"'
    msg.attach(attachment)

    # ── send ───────────────────────────────────────────────────────────────────
    print(f"Connecting to {SMTP_HOST}:{SMTP_PORT} …")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER, PASSWORD)
        server.sendmail(SENDER, recipients, msg.as_string())

    print(f"Sent to: {', '.join(recipients)}")
    print(f"Subject: {subject}")
    print(f"Attachment: {DASHBOARD_FILE} ({len(html_bytes):,} bytes)")


if __name__ == "__main__":
    send()
