"""
=============================================================
  TRADING SIGNAL BOT v2  —  FREE APIs ONLY
  Covers: Crypto (Binance public) · Forex · pump.fun
  Alerts:  Telegram only
=============================================================
"""

# ─────────────────────────────────────────────
#  ⚙️  CONFIG — FILL IN YOUR CREDENTIALS HERE
# ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID   = "PASTE_YOUR_TELEGRAM_CHAT_ID_HERE"   # DM @userinfobot on Telegram to get this

# ─────────────────────────────────────────────
#  📊  SIGNAL SETTINGS (adjust freely)
# ─────────────────────────────────────────────

CRYPTO_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT",
]

FOREX_PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD", "EUR/GBP",
    "EUR/JPY", "GBP/JPY",
]

RSI_OVERSOLD          = 30     # triggers BUY signal
RSI_OVERBOUGHT        = 70     # triggers SELL signal
FOREX_MOVE_PCT        = 0.3    # alert on ≥0.3% move since last scan
PUMPFUN_GRAD_MCAP     = 69_000 # alert when token mcap is within 10% of $69k
SCAN_INTERVAL_SECONDS = 60

# ─────────────────────────────────────────────
#  📦  IMPORTS
# ─────────────────────────────────────────────

import time
import requests
import traceback
import numpy as np
from datetime import datetime, timezone

# ─────────────────────────────────────────────
#  📤  TELEGRAM ALERT
# ─────────────────────────────────────────────

def alert(subject: str, body: str):
    message = f"*{subject}*\n{body}"
    print(f"[ALERT] {subject}")
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10
        ).raise_for_status()
    except Exception as e:
        print(f"[Telegram error] {e}")

# ─────────────────────────────────────────────
#  📈  CRYPTO — Binance public REST (no key)
# ─────────────────────────────────────────────

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

def compute_rsi(closes: list, period: int = 14) -> float:
    arr   = np.array(closes, dtype=float)
    delta = np.diff(arr)
    gain  = np.where(delta > 0, delta, 0.0)
    loss  = np.where(delta < 0, -delta, 0.0)
    ag    = np.mean(gain[:period])
    al    = np.mean(loss[:period])
    if al == 0:
        return 100.0
    for i in range(period, len(gain)):
        ag = (ag * (period - 1) + gain[i]) / period
        al = (al * (period - 1) + loss[i]) / period
    return round(100 - (100 / (1 + ag / al)), 2) if al else 100.0


def check_crypto():
    for pair in CRYPTO_PAIRS:
        try:
            r      = requests.get(BINANCE_KLINES,
                                  params={"symbol": pair, "interval": "1h", "limit": 100},
                                  timeout=10)
            closes = [float(k[4]) for k in r.json()]
            rsi    = compute_rsi(closes)
            price  = closes[-1]

            if rsi <= RSI_OVERSOLD:
                alert(f"🟢 BUY — {pair}",
                      f"RSI: {rsi} (oversold)\nPrice: ${price:,.4f}\nTime: {now()}")
            elif rsi >= RSI_OVERBOUGHT:
                alert(f"🔴 SELL — {pair}",
                      f"RSI: {rsi} (overbought)\nPrice: ${price:,.4f}\nTime: {now()}")
            else:
                print(f"  {pair}: RSI {rsi} — no signal")
        except Exception:
            print(f"[{pair} error]\n{traceback.format_exc()}")

# ─────────────────────────────────────────────
#  💱  FOREX — open.er-api.com (free, no key)
# ─────────────────────────────────────────────

_forex_prev: dict = {}

def check_forex():
    for pair in FOREX_PAIRS:
        try:
            base, quote = pair.split("/")
            data  = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10).json()
            rate  = data["rates"].get(quote)
            if rate is None:
                continue

            prev = _forex_prev.get(pair)
            if prev is not None:
                chg = ((rate - prev) / prev) * 100
                if abs(chg) >= FOREX_MOVE_PCT:
                    direction = "📈 UP" if chg > 0 else "📉 DOWN"
                    alert(f"{direction} — {pair} moved {chg:+.2f}%",
                          f"Rate: {rate:.5f}\nPrevious: {prev:.5f}\nTime: {now()}")
                else:
                    print(f"  {pair}: {rate:.5f} (\u0394{chg:+.3f}%) — no signal")
            else:
                print(f"  {pair}: {rate:.5f} (first reading)")

            _forex_prev[pair] = rate
        except Exception:
            print(f"[{pair} error]\n{traceback.format_exc()}")

# ─────────────────────────────────────────────
#  🚀  pump.fun — public API (free)
# ─────────────────────────────────────────────

PUMPFUN_API    = "https://frontend-api.pump.fun/coins?limit=50&sort=market_cap&order=DESC&includeNsfw=false"
_alerted_mints = set()

def check_pumpfun():
    try:
        coins = requests.get(PUMPFUN_API, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0"}).json()
        for coin in coins:
            mint = coin.get("mint", "")
            name = coin.get("name", "?")
            sym  = coin.get("symbol", "?")
            mcap = coin.get("usd_market_cap", 0) or 0

            if mcap >= PUMPFUN_GRAD_MCAP * 0.9 and mint not in _alerted_mints:
                graduated = coin.get("raydium_pool") is not None
                status    = "✅ GRADUATED to Raydium" if graduated else "⚠️ Near graduation"
                alert(f"🚀 pump.fun — {name} ({sym}) {status}",
                      f"Market Cap: ${mcap:,.0f}\n"
                      f"https://pump.fun/{mint}\n"
                      f"Time: {now()}")
                _alerted_mints.add(mint)
    except Exception:
        print(f"[pump.fun error]\n{traceback.format_exc()}")

# ─────────────────────────────────────────────
#  🕐  UTILS + MAIN LOOP
# ─────────────────────────────────────────────

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main():
    print("=" * 50)
    print("  Trading Signal Bot v2 — Telegram only")
    print(f"  Crypto : {len(CRYPTO_PAIRS)} pairs")
    print(f"  Forex  : {len(FOREX_PAIRS)} pairs")
    print(f"  Scan   : every {SCAN_INTERVAL_SECONDS}s")
    print("=" * 50)

    alert("🤖 Signal Bot v2 is live!", "Watching crypto, forex & pump.fun.\nAll free APIs.")

    while True:
        print(f"\n[{now()}] scanning...")
        check_crypto()
        check_forex()
        check_pumpfun()
        print(f"Done. Next scan in {SCAN_INTERVAL_SECONDS}s.")
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
