# === AI Volume Momentum Agent ===
# Tracks top-1000 crypto coins on CoinMarketCap
# Alerts when any coin’s 24h volume increases 5 days in a row.

import requests, sqlite3, datetime, time

# === CONFIG (put your keys here manually) ===
CMC_API_KEY = "1893919c04494bb093be2c99d74b97a1"
TELEGRAM_BOT_TOKEN = "8511332304:AAGPqAJrQzSTqqhR1TxTGMEqFH-LGf_o5Mc"
TELEGRAM_CHAT_ID = "6673592368"

# === DATABASE ===
DB = "volumes.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS volume (coin TEXT, date TEXT, volume REAL)")
conn.commit()

# === TELEGRAM ALERT ===
def send_telegram(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured; printing instead:\n", msg)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("⚠️ Telegram error:", e)

# === FETCH VOLUMES FROM COINMARKETCAP ===
def fetch_volumes():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"limit": 1000, "sort": "market_cap", "sort_dir": "desc"}
    try:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as e:
        send_telegram(f"⚠️ Error fetching data: {e}")
        return 0
    today = datetime.date.today().isoformat()
    count = 0
    for coin in data:
        vol = coin["quote"]["USD"]["volume_24h"]
        if vol >= 250_000:
            cur.execute("INSERT INTO volume VALUES (?, ?, ?)", (coin["symbol"], today, vol))
            count += 1
    conn.commit()
    print(f"✅ Logged {count} coins for {today}")
    return count

# === CHECK 5-DAY UPTRENDS ===
def check_uptrends():
    coins = [r[0] for r in cur.execute("SELECT DISTINCT coin FROM volume")]
    alerts = []
    for coin in coins:
        rows = cur.execute(
            "SELECT volume FROM volume WHERE coin=? ORDER BY date DESC LIMIT 5", (coin,)
        ).fetchall()
        if len(rows) == 5:
            vols = [r[0] for r in rows][::-1]  # oldest → newest
            if all(vols[i] < vols[i+1] for i in range(4)):
                growth = (vols[-1] / vols[0] - 1) * 100
                alerts.append((coin, growth))
    return alerts

# === MAIN LOOP ===
def main():
    count = fetch_volumes()
    if count == 0:
        return
    alerts = check_uptrends()
    if alerts:
        msg = "🚀 POSSIBLE BREAKOUTS DETECTED:\n"
        for coin, growth in sorted(alerts, key=lambda x: x[1], reverse=True):
            msg += f"• {coin}: volume +{growth:.1f}% over 5 days\n"
        print(msg)
        send_telegram(msg)
    else:
        msg = "No 5-day consecutive volume rises detected today."
        print(msg)
        send_telegram(msg)

# === AUTONOMOUS MODE ===
if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            send_telegram(f"⚠️ Volume agent crashed: {e}")
            print("⚠️ Error:", e)
        print("⏳ Sleeping 24 hours before next run...")
        time.sleep(86400)
