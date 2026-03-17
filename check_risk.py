"""
Risk Alert System
Fetches live prices, calculates log-linear regression risk scores,
and sends email + push notifications when thresholds are crossed.
"""

import os
import math
import json
import smtplib
import urllib.request
import urllib.error
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Configuration ──────────────────────────────────────────────────────────────

# Risk threshold: alert fires when risk drops AT OR BELOW this level
ALERT_THRESHOLD = 0.35  # Change this to whatever you decide

# Your watchlist: add as many tickers as you like
# Format: { "TICKER": { "name": "Full Name", "inception": "YYYY-MM-DD", "allocation_pct": X } }
WATCHLIST = {
    # ── Mega Cap Tech ──────────────────────────────────────────────
    "MSFT":   {"name": "Microsoft",              "inception": "1986-03-13", "allocation_pct": 3},
    "AMZN":   {"name": "Amazon",                 "inception": "1997-05-15", "allocation_pct": 3},
    "NVDA":   {"name": "Nvidia",                 "inception": "1999-01-22", "allocation_pct": 3},
    "META":   {"name": "Meta Platforms",         "inception": "2012-05-18", "allocation_pct": 3},
    "AAPL":   {"name": "Apple",                  "inception": "1980-12-12", "allocation_pct": 3},
    "GOOG":   {"name": "Alphabet",               "inception": "2004-08-19", "allocation_pct": 3},
    "IBM":    {"name": "IBM",                    "inception": "1962-01-02", "allocation_pct": 2},
    "ADBE":   {"name": "Adobe",                  "inception": "1986-08-13", "allocation_pct": 2},
    # ── Software / Cloud ───────────────────────────────────────────
    "ORCL":   {"name": "Oracle",                 "inception": "1986-03-12", "allocation_pct": 2},
    "PLTR":   {"name": "Palantir",               "inception": "2020-09-30", "allocation_pct": 2},
    "SHOP":   {"name": "Shopify",                "inception": "2015-05-21", "allocation_pct": 2},
    "PATH":   {"name": "UiPath",                 "inception": "2021-04-21", "allocation_pct": 2},
    "CSCO":   {"name": "Cisco",                  "inception": "1990-02-16", "allocation_pct": 2},
    # ── Semiconductors ────────────────────────────────────────────
    "AVGO":   {"name": "Broadcom",               "inception": "2009-08-06", "allocation_pct": 2},
    "AMD":    {"name": "AMD",                    "inception": "1972-09-27", "allocation_pct": 2},
    "INTC":   {"name": "Intel",                  "inception": "1971-10-13", "allocation_pct": 2},
    # ── Consumer / Streaming ──────────────────────────────────────
    "NFLX":   {"name": "Netflix",                "inception": "2002-05-23", "allocation_pct": 2},
    "SPOT":   {"name": "Spotify",                "inception": "2018-04-03", "allocation_pct": 2},
    "TSLA":   {"name": "Tesla",                  "inception": "2010-06-29", "allocation_pct": 2},
    "COST":   {"name": "Costco",                 "inception": "1985-12-05", "allocation_pct": 2},
    "WMT":    {"name": "Walmart",                "inception": "1972-08-25", "allocation_pct": 2},
    "TGT":    {"name": "Target",                 "inception": "1967-01-03", "allocation_pct": 2},
    "BABA":   {"name": "Alibaba",                "inception": "2014-09-19", "allocation_pct": 2},
    "SONY":   {"name": "Sony Group",             "inception": "1970-09-01", "allocation_pct": 2},
    "TTWO":   {"name": "Take-Two Interactive",   "inception": "1993-09-24", "allocation_pct": 2},
    # ── Financials ────────────────────────────────────────────────
    "JPM":    {"name": "JPMorgan Chase",         "inception": "1969-01-02", "allocation_pct": 2},
    "BRK-B":  {"name": "Berkshire Hathaway B",   "inception": "1996-05-09", "allocation_pct": 2},
    "BLK":    {"name": "BlackRock",              "inception": "1999-10-01", "allocation_pct": 2},
    "HOOD":   {"name": "Robinhood",              "inception": "2021-07-29", "allocation_pct": 2},
    "IFC.TO": {"name": "Intact Financial",       "inception": "2004-02-12", "allocation_pct": 2},
    # ── Telecom ───────────────────────────────────────────────────
    "TMUS":   {"name": "T-Mobile US",            "inception": "2013-05-01", "allocation_pct": 2},
    # ── Energy ────────────────────────────────────────────────────
    "CVX":    {"name": "Chevron",                "inception": "1970-01-02", "allocation_pct": 2},
    "DVN":    {"name": "Devon Energy",           "inception": "1988-01-04", "allocation_pct": 2},
    # ── Uranium / Nuclear ─────────────────────────────────────────
    "URA":    {"name": "Global X Uranium ETF",   "inception": "2010-11-04", "allocation_pct": 2},
    "UEC":    {"name": "Uranium Energy Corp",    "inception": "2007-01-03", "allocation_pct": 2},
    "CCO.TO": {"name": "Cameco",                 "inception": "1991-01-02", "allocation_pct": 2},
    "UUUU":   {"name": "Energy Fuels",           "inception": "2012-01-03", "allocation_pct": 2},
    # ── Rare Earth / Materials ────────────────────────────────────
    "MP":     {"name": "MP Materials",           "inception": "2020-11-17", "allocation_pct": 2},
    "USAR":   {"name": "USA Rare Earth",         "inception": "2024-01-02", "allocation_pct": 2},
    "ALB":    {"name": "Albemarle",              "inception": "1994-02-28", "allocation_pct": 2},
    "LAC":    {"name": "Lithium Americas",       "inception": "2020-09-01", "allocation_pct": 2},
    "AG":     {"name": "First Majestic Silver",  "inception": "2011-05-10", "allocation_pct": 2},
    # ── Crypto / Bitcoin Mining ───────────────────────────────────
    "MSTR":   {"name": "MicroStrategy",          "inception": "1998-06-11", "allocation_pct": 2},
    "IREN":   {"name": "Iris Energy",            "inception": "2021-11-18", "allocation_pct": 2},
    "BMNR":   {"name": "Bitmine Immersion",      "inception": "2022-06-01", "allocation_pct": 2},
    "APLD":   {"name": "Applied Digital",        "inception": "2022-04-01", "allocation_pct": 2},
    # ── Defence / Industrial ──────────────────────────────────────
    "AVAV":   {"name": "AeroVironment",          "inception": "2007-01-26", "allocation_pct": 2},
    "RR.L":   {"name": "Rolls-Royce",            "inception": "1987-01-01", "allocation_pct": 2},
    # ── EV / Mobility ─────────────────────────────────────────────
    "XPEV":   {"name": "XPeng",                  "inception": "2020-08-27", "allocation_pct": 2},
    "RIVN":   {"name": "Rivian",                 "inception": "2021-11-10", "allocation_pct": 2},
    # ── Emerging / Small Cap ──────────────────────────────────────
    "ONDS":   {"name": "Ondas Holdings",         "inception": "2018-01-02", "allocation_pct": 1},
    "SRFM":   {"name": "Surf Air Mobility",      "inception": "2023-07-27", "allocation_pct": 1},
    "CCO":    {"name": "Clear Channel Outdoor",  "inception": "2005-11-11", "allocation_pct": 1},
}

# Notification settings (injected via GitHub Secrets)
GMAIL_USER      = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS  = os.environ.get("GMAIL_APP_PASS", "")
ALERT_EMAIL_TO  = os.environ.get("ALERT_EMAIL_TO", "")
NTFY_TOPIC      = os.environ.get("NTFY_TOPIC", "")   # e.g. "dannypeters-risk-alerts"


# ── Data Fetching ──────────────────────────────────────────────────────────────

def fetch_history(ticker):
    """Fetch full price history from Yahoo Finance."""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=max"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        points = [
            (date.fromtimestamp(t), c)
            for t, c in zip(timestamps, closes)
            if c is not None and c > 0
        ]
        return sorted(points, key=lambda x: x[0])
    except Exception as e:
        print(f"  Warning: Yahoo fetch failed for {ticker}: {e}")
        return []


# ── Risk Calculation ───────────────────────────────────────────────────────────

def days_since(d, inception):
    return (d - inception).days

def linear_regression(xs, ys):
    n = len(xs)
    sx = sum(xs); sy = sum(ys)
    sxy = sum(x*y for x,y in zip(xs,ys))
    sx2 = sum(x*x for x in xs)
    slope = (n*sxy - sx*sy) / (n*sx2 - sx*sx)
    intercept = (sy - slope*sx) / n
    return slope, intercept

def calculate_risk(history, inception_str):
    inception = date.fromisoformat(inception_str)
    # Filter to inception date+
    history = [(d, p) for d, p in history if d >= inception and p > 0]
    if len(history) < 30:
        return None, None, None, None

    xs = [days_since(d, inception) for d, p in history]
    ys = [math.log10(p) for d, p in history]

    slope, intercept = linear_regression(xs, ys)
    predicted = [slope*x + intercept for x in xs]
    residuals = [y - p for y, p in zip(ys, predicted)]

    min_res = min(residuals)
    max_res = max(residuals)
    span = max_res - min_res

    risks = [(r - min_res) / span for r in residuals]

    current_price = history[-1][1]
    current_risk  = risks[-1]
    current_days  = xs[-1]
    fair_value    = 10 ** (slope * current_days + intercept)
    deviation     = (current_price - fair_value) / fair_value

    return current_price, current_risk, fair_value, deviation


# ── Risk Zone Label ────────────────────────────────────────────────────────────

def risk_zone(r):
    if r < 0.35: return "🟢 ACCUMULATE"
    if r < 0.65: return "🟡 NEUTRAL"
    if r < 0.85: return "🟠 CAUTION"
    return "🔴 EXTREME"

def risk_zone_plain(r):
    """Emoji-free version for push notifications."""
    if r < 0.35: return "ACCUMULATE"
    if r < 0.65: return "NEUTRAL"
    if r < 0.85: return "CAUTION"
    return "EXTREME"


# ── Notifications ──────────────────────────────────────────────────────────────

def send_email(subject, html_body, text_body):
    if not all([GMAIL_USER, GMAIL_APP_PASS, ALERT_EMAIL_TO]):
        print("  Email not configured, skipping.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = ALERT_EMAIL_TO
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.sendmail(GMAIL_USER, ALERT_EMAIL_TO, msg.as_string())
        print(f"  ✅ Email sent to {ALERT_EMAIL_TO}")
    except Exception as e:
        print(f"  ❌ Email failed: {e}")


def send_push(title, message, priority="default"):
    if not NTFY_TOPIC:
        print("  Push not configured, skipping.")
        return
    try:
        data = message.encode("utf-8")
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=data,
            headers={
                "Title": title.encode("utf-8").decode("latin-1", errors="replace"),
                "Priority": priority,
                "Tags": "chart_with_upwards_trend",
                "Content-Type": "text/plain; charset=utf-8",
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  ✅ Push notification sent to ntfy.sh/{NTFY_TOPIC}")
    except Exception as e:
        print(f"  ❌ Push notification failed: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────

# ── State file for tracking which tickers were already in alert zone ──────────
STATE_FILE = "alert_state.json"

def load_state():
    """Load previous run's alert state."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"in_zone": []}

def save_state(in_zone_tickers):
    """Save current alert state for next run."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"in_zone": in_zone_tickers, "updated": str(date.today())}, f)
    except Exception as e:
        print(f"  ⚠ Could not save state: {e}")


def main():
    today = date.today()
    print(f"\n{'='*60}")
    print(f"Risk Alert Check — {today.strftime('%A %B %d, %Y')}")
    print(f"Threshold: {ALERT_THRESHOLD}")
    print(f"{'='*60}\n")

    # Load previous state to detect NEW entries into accumulate zone
    prev_state   = load_state()
    prev_in_zone = set(prev_state.get("in_zone", []))

    results      = []
    alerts       = []   # ALL stocks currently in zone (for daily summary)
    new_alerts   = []   # stocks that NEWLY entered the zone today

    for ticker, cfg in WATCHLIST.items():
        print(f"Checking {ticker} ({cfg['name']})...")
        history = fetch_history(ticker)

        if not history:
            print(f"  ⚠  No data returned for {ticker}\n")
            continue

        price, risk, fair_value, deviation = calculate_risk(history, cfg["inception"])

        if risk is None:
            print(f"  ⚠  Insufficient data for {ticker}\n")
            continue

        zone    = risk_zone(risk)
        dev_pct = deviation * 100 if deviation is not None else 0
        print(f"  Price:      ${price:.2f}")
        if fair_value:
            print(f"  Fair Value: ${fair_value:.2f}  ({dev_pct:+.1f}%)")
        print(f"  Risk:       {risk:.3f}  {zone}")
        print(f"  Allocation: {cfg['allocation_pct']}% of portfolio\n")

        result = {
            "ticker":     ticker,
            "name":       cfg["name"],
            "price":      price,
            "risk":       risk,
            "fair_value": fair_value,
            "deviation":  deviation,
            "zone":       zone,
            "allocation": cfg["allocation_pct"],
        }
        results.append(result)

        if risk <= ALERT_THRESHOLD:
            alerts.append(result)
            # Only trigger urgent notification if this is NEW to the zone
            if ticker not in prev_in_zone:
                new_alerts.append(result)
                print(f"  🚨 NEW ENTRY: {ticker} just entered accumulate zone at {risk:.3f}\n")
            else:
                print(f"  ✅ Still in zone: {ticker} {risk:.3f}\n")

    # Sort alerts by risk (lowest/cheapest first)
    alerts.sort(key=lambda x: x["risk"])
    new_alerts.sort(key=lambda x: x["risk"])

    # Save new state
    save_state([r["ticker"] for r in alerts])

    print(f"\n── Summary ──────────────────────────────────────────────")
    print(f"In accumulate zone: {len(alerts)} stocks")
    print(f"Newly entered zone: {len(new_alerts)} stocks")

    # ── Notifications ─────────────────────────────────────────────────────────
    if new_alerts:
        # Urgent push + email for newly entered stocks
        print("\nSending NEW ENTRY alert notifications...")
        _send_alert_notifications(new_alerts, alerts, results, today, is_new=True)

    # Always send daily summary email with full zone status
    print("\nSending daily summary...")
    _send_daily_summary(results, alerts, today)


def _send_alert_notifications(new_alerts, zone_alerts, all_results, today, is_new=True):
    """Send urgent notification for stocks newly entering the accumulate zone."""
    tickers_str = ", ".join(a["ticker"] for a in new_alerts)
    subject = f"🚨 NEW Buy Zone Entry: {tickers_str} — {today}"

    alert_lines = "\n".join(
        f"• {a['ticker']} ({a['name']}): Risk {a['risk']:.3f} | "
        f"Price ${a['price']:.2f}" +
        (f" | FV ${a['fair_value']:.2f} ({a['deviation']*100:+.1f}%)" if a['fair_value'] else "") +
        f" | Alloc {a['allocation']}%"
        for a in new_alerts
    )

    currently_in = "\n".join(
        f"  {a['ticker']}: {a['risk']:.3f} — ${a['price']:.2f}"
        for a in zone_alerts
    ) or "  None"

    text_body = f"""🚨 New Buy Zone Entry — {today}

{len(new_alerts)} stock(s) just entered the ACCUMULATE zone (risk <= {ALERT_THRESHOLD}):

{alert_lines}

All stocks currently in zone ({len(zone_alerts)} total):
{currently_in}

—
Portfolio Risk Alert System
"""
    html_body = _build_html_email(alerts=new_alerts, zone_alerts=zone_alerts, all_results=all_results, today=today, is_alert=True)
    send_email(subject, html_body, text_body)

    # Individual push per new entry (high priority)
    for a in new_alerts:
        fv_str = f" | FV ${a['fair_value']:.2f}" if a['fair_value'] else ""
        send_push(
            title=f"NEW BUY ZONE: {a['ticker']}",
            message=f"Risk: {a['risk']:.3f} | ${a['price']:.2f}{fv_str} | {risk_zone_plain(a['risk'])}",
            priority="urgent"
        )

    # One summary push for full zone list
    if len(zone_alerts) > len(new_alerts):
        others = [a for a in zone_alerts if a["ticker"] not in [n["ticker"] for n in new_alerts]]
        if others:
            send_push(
                title=f"Also in zone: {', '.join(a['ticker'] for a in others[:5])}",
                message="\n".join(f"{a['ticker']}: {a['risk']:.3f}" for a in others[:8]),
                priority="default"
            )


def _send_daily_summary(results, zone_alerts, today):
    """Send daily summary email + push with full zone status."""
    in_zone_count = len(zone_alerts)
    subject = (
        f"🟢 {in_zone_count} stock(s) in buy zone — {today}"
        if in_zone_count > 0
        else f"📊 Daily Risk Summary — {today} — no stocks in buy zone"
    )

    zone_lines = "\n".join(
        f"  {a['ticker']}: {a['risk']:.3f} — ${a['price']:.2f}"
        for a in zone_alerts
    ) or "  None currently"

    text_body = f"""Daily Risk Summary — {today}
Threshold: {ALERT_THRESHOLD}

Stocks in Accumulate Zone ({in_zone_count}):
{zone_lines}

Full Portfolio:
{_text_summary_table(results)}

—
Portfolio Risk Alert System
"""
    html_body = _build_html_email(alerts=[], zone_alerts=zone_alerts, all_results=results, today=today, is_alert=False)
    send_email(subject, html_body, text_body)

    # Push: list all stocks in zone
    if zone_alerts:
        lines = [f"{a['ticker']}: {a['risk']:.3f}" for a in zone_alerts]
        send_push(
            title=f"Daily Summary: {in_zone_count} in buy zone",
            message="In zone: " + ", ".join(a["ticker"] for a in zone_alerts) +
                    f"\nThreshold: {ALERT_THRESHOLD}",
            priority="default"
        )
    else:
        # Still send a daily push so you know the system ran
        send_push(
            title=f"Daily Summary - {today}",
            message=f"No stocks below {ALERT_THRESHOLD} today. Lowest: " +
                    min(results, key=lambda x: x["risk"])["ticker"] + " " +
                    f"{min(results, key=lambda x: x['risk'])['risk']:.3f}"
                    if results else "No data",
            priority="min"
        )


def _text_summary_table(results):
    lines = []
    for r in results:
        lines.append(
            f"  {r['ticker']:<6} Risk: {r['risk']:.3f}  {r['zone']:<20}  "
            f"${r['price']:.2f}  (FV ${r['fair_value']:.2f}  {r['deviation']*100:+.1f}%)"
        )
    return "\n".join(lines)


def _risk_color(risk):
    if risk < 0.35: return "#34d399"
    if risk < 0.65: return "#fbbf24"
    if risk < 0.85: return "#f87171"
    return "#ef4444"


def _build_html_email(alerts, all_results=None, today=None, is_alert=False, zone_alerts=None):
    alert_banner = ""
    if is_alert and alerts:
        tickers = ", ".join(a["ticker"] for a in alerts)
        alert_banner = f"""
        <div style="background:#ef4444;color:#fff;padding:16px 24px;border-radius:6px;margin-bottom:24px;font-size:18px;font-weight:bold;">
            🚨 NEW BUY ZONE: {tickers}
        </div>"""
    elif zone_alerts:
        tickers = ", ".join(a["ticker"] for a in zone_alerts)
        alert_banner = f"""
        <div style="background:#16a34a;color:#fff;padding:12px 24px;border-radius:6px;margin-bottom:24px;font-size:15px;font-weight:bold;">
            🟢 Currently in buy zone: {tickers}
        </div>"""

    rows = ""
    for r in all_results:
        color = _risk_color(r["risk"])
        bar_width = int(r["risk"] * 200)
        rows += f"""
        <tr style="border-bottom:1px solid #1e2029;">
            <td style="padding:12px 16px;font-weight:bold;">{r['ticker']}</td>
            <td style="padding:12px 16px;color:#888;">{r['name']}</td>
            <td style="padding:12px 16px;">${r['price']:.2f}</td>
            <td style="padding:12px 16px;">
                <span style="color:{color};font-weight:bold;">{r['risk']:.3f}</span>
                <div style="background:#1e2029;border-radius:3px;height:6px;width:200px;margin-top:4px;">
                    <div style="background:{color};width:{bar_width}px;height:6px;border-radius:3px;"></div>
                </div>
            </td>
            <td style="padding:12px 16px;color:{color};">{r['zone']}</td>
            <td style="padding:12px 16px;">${r['fair_value']:.2f}</td>
            <td style="padding:12px 16px;color:{'#f87171' if r['deviation']>0 else '#34d399'};">{r['deviation']*100:+.1f}%</td>
            <td style="padding:12px 16px;color:#888;">{r['allocation']}%</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0c0e;color:#dde0e8;font-family:'Helvetica Neue',Arial,sans-serif;">
<div style="max-width:800px;margin:0 auto;padding:32px 24px;">

    <div style="margin-bottom:24px;">
        <div style="font-size:22px;font-weight:800;letter-spacing:-0.02em;">📊 Risk Alert System</div>
        <div style="color:#565c6d;font-size:13px;margin-top:4px;">{today.strftime('%A, %B %d, %Y')} · Threshold: {ALERT_THRESHOLD}</div>
    </div>

    {alert_banner}

    <table style="width:100%;border-collapse:collapse;background:#12141a;border-radius:6px;overflow:hidden;">
        <thead>
            <tr style="background:#191c25;color:#565c6d;font-size:11px;text-transform:uppercase;letter-spacing:0.1em;">
                <th style="padding:10px 16px;text-align:left;">Ticker</th>
                <th style="padding:10px 16px;text-align:left;">Name</th>
                <th style="padding:10px 16px;text-align:left;">Price</th>
                <th style="padding:10px 16px;text-align:left;">Risk</th>
                <th style="padding:10px 16px;text-align:left;">Zone</th>
                <th style="padding:10px 16px;text-align:left;">Fair Value</th>
                <th style="padding:10px 16px;text-align:left;">Deviation</th>
                <th style="padding:10px 16px;text-align:left;">Allocation</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>

    <div style="margin-top:24px;color:#565c6d;font-size:11px;">
        Risk = log-linear regression deviation, min/max normalised. Not financial advice.
    </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
