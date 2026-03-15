# Risk Alert System

Sends daily email + push notifications when stocks drop into the Accumulate zone.

## Setup (10 minutes)

### 1. Create a new GitHub repo
Go to github.com → New repository → name it `risk-alerts` → Public → Create.

Upload both files:
- `check_risk.py`
- `.github/workflows/risk_alert.yml`

### 2. Set up push notifications (ntfy.sh)
1. Install **ntfy** app on your phone (iOS or Android — search "ntfy")
2. Open the app → tap **+** → Subscribe to topic
3. Pick a unique topic name, e.g. `dannypeters-risk-alerts` (make it hard to guess)
4. Done — your phone will now receive push notifications to that topic

### 3. Set up Gmail sending
1. Go to your Google Account → Security → 2-Step Verification (must be ON)
2. Then go to: myaccount.google.com/apppasswords
3. Create a new app password → name it "Risk Alerts"
4. Copy the 16-character password it gives you

### 4. Add GitHub Secrets
In your GitHub repo → Settings → Secrets and variables → Actions → New repository secret

Add these four secrets:

| Secret name    | Value                                      |
|----------------|--------------------------------------------|
| GMAIL_USER     | your.email@gmail.com                       |
| GMAIL_APP_PASS | the 16-char app password from step 3       |
| ALERT_EMAIL_TO | email address to send alerts TO            |
| NTFY_TOPIC     | your topic name e.g. dannypeters-risk-alerts |

### 5. Test it
Go to your repo → Actions tab → "Daily Risk Alert" → Run workflow → Run workflow.
Check your email and phone within 30 seconds.

---

## Customising

### Change the alert threshold
In `check_risk.py`, line 14:
```python
ALERT_THRESHOLD = 0.35  # change this number
```

### Add a new stock to the watchlist
In `check_risk.py`, add to the `WATCHLIST` dict:
```python
"AAPL": {
    "name": "Apple Inc.",
    "inception": "1980-12-12",
    "allocation_pct": 20,
},
```

### Change when alerts run
In `.github/workflows/risk_alert.yml`, change the cron line:
```
- cron: '0 22 * * 1-5'   # 10pm UTC weekdays (after US close)
- cron: '0 7 * * 1-5'    # 7am UTC weekdays (before US open)
```

---

## How the risk score works

1. **Log-linear regression**: fits a straight line through `log₁₀(price)` vs days since IPO
2. **Residual**: actual log price minus predicted log price (how far above/below the trend)
3. **Normalisation**: scales residual between 0 (most undervalued ever) and 1 (most overvalued ever)

| Risk    | Zone       | Meaning                              |
|---------|------------|--------------------------------------|
| 0–0.35  | Accumulate | Below long-run trend, historically cheap |
| 0.35–0.65 | Neutral  | Around fair value                    |
| 0.65–0.85 | Caution  | Above trend, exercise caution        |
| 0.85–1.0  | Extreme  | Historically overvalued              |

Not financial advice.
