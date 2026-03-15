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
    "URA": {
        "name": "Global X Uranium ETF",
        "inception": "2010-11-04",
        "allocation_pct": 50,   # your target % of portfolio
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "inception": "1986-03-13",
        "allocation_pct": 50,
    },
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
                "Title": title,
                "Priority": priority,
                "Tags": "chart_with_upwards_trend",
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  ✅ Push notification sent to ntfy.sh/{NTFY_TOPIC}")
    except Exception as e:
        print(f"  ❌ Push notification failed: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"\n{'='*60}")
    print(f"Risk Alert Check — {today.strftime('%A %B %d, %Y')}")
    print(f"Threshold: {ALERT_THRESHOLD}")
    print(f"{'='*60}\n")

    results = []
    alerts  = []

    for ticker, cfg in WATCHLIST.items():
        print(f"Checking {ticker} ({cfg['name']})...")
        history = fetch_history(ticker)

        if not history:
            print(f"  ⚠️  No data returned for {ticker}\n")
            continue

        price, risk, fair_value, deviation = calculate_risk(history, cfg["inception"])

        if risk is None:
            print(f"  ⚠️  Insufficient data for {ticker}\n")
            continue

        zone = risk_zone(risk)
        dev_pct = deviation * 100
        print(f"  Price:      ${price:.2f}")
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
            print(f"  🚨 ALERT: {ticker} risk {risk:.3f} is at or below threshold {ALERT_THRESHOLD}\n")

    # ── Build and send notifications ──────────────────────────────────────────

    if alerts:
        _send_alert_notifications(alerts, results, today)
    else:
        print("No tickers in alert zone today.")
        _send_daily_summary(results, today)


def _send_alert_notifications(alerts, all_results, today):
    alert_lines = "\n".join(
        f"• {a['ticker']} ({a['name']}): Risk {a['risk']:.3f} {a['zone']} | "
        f"Price ${a['price']:.2f} | Fair Value ${a['fair_value']:.2f} ({a['deviation']*100:+.1f}%) | "
        f"Allocation {a['allocation']}%"
        for a in alerts
    )

    subject = f"🚨 Risk Alert: {', '.join(a['ticker'] for a in alerts)} in Buy Zone — {today}"

    text_body = f"""Risk Alert — {today}

The following stocks have entered the ACCUMULATE zone (risk ≤ {ALERT_THRESHOLD}):

{alert_lines}

Full Portfolio Status:
{_text_summary_table(all_results)}

—
Sent by your Risk Alert System
"""

    html_body = _build_html_email(alerts, all_results, today, is_alert=True)

    send_email(subject, html_body, text_body)

    for a in alerts:
        send_push(
            title=f"🚨 {a['ticker']} Buy Zone!",
            message=f"Risk: {a['risk']:.3f} | Price: ${a['price']:.2f} | FV: ${a['fair_value']:.2f} ({a['deviation']*100:+.1f}%) — {a['zone']}",
            priority="high"
        )


def _send_daily_summary(results, today):
    """Send a daily summary email + push even when no alerts fire."""
    subject = f"📊 Daily Risk Summary — {today}"
    text_body = f"""Daily Risk Summary — {today}

No tickers in alert zone today (threshold: {ALERT_THRESHOLD})

{_text_summary_table(results)}

—
Sent by your Risk Alert System
"""
    html_body = _build_html_email([], results, today, is_alert=False)
    send_email(subject, html_body, text_body)

    # Push summary — one line per ticker
    lines = [f"{r['ticker']}: {r['risk']:.3f} {r['zone']}" for r in results]
    send_push(
        title=f"📊 Daily Risk Summary — {today}",
        message="\n".join(lines) + f"\nThreshold: {ALERT_THRESHOLD}",
        priority="default"
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


def _build_html_email(alerts, all_results, today, is_alert):
    alert_banner = ""
    if is_alert:
        tickers = ", ".join(a["ticker"] for a in alerts)
        alert_banner = f"""
        <div style="background:#ef4444;color:#fff;padding:16px 24px;border-radius:6px;margin-bottom:24px;font-size:18px;font-weight:bold;">
            🚨 {tickers} — Risk below {ALERT_THRESHOLD} (Accumulate Zone)
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
