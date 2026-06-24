#!/usr/bin/env python3
"""
rsi_check.py — runs ONCE, then exits. Designed for GitHub Actions.

Checks whether RSI just crossed a threshold on the most recently CLOSED
candle, and sends an ntfy push if so. Stateless: each run reads only
Hyperliquid candle history, so no database or saved state is needed.
"""

import os
import time
import requests

# ─────────── settings you can edit ───────────
COIN       = "BTC"     # Hyperliquid symbol: BTC, ETH, SOL, HYPE, ...
INTERVAL   = "5m"      # 1m 3m 5m 15m 30m 1h 2h 4h 1d ...
RSI_PERIOD = 14
UPPER      = 70        # overbought
LOWER      = 30        # oversold
# ──────────────────────────────────────────────

NTFY_TOPIC  = os.environ.get("NTFY_TOPIC", "")   # comes from a GitHub Secret
NTFY_SERVER = "https://ntfy.sh"

INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
}


def fetch_closes(coin, interval, lookback=250):
    span = INTERVAL_MS[interval]
    end = int(time.time() * 1000)
    start = end - span * lookback
    r = requests.post(
        "https://api.hyperliquid.xyz/info",
        json={"type": "candleSnapshot",
              "req": {"coin": coin, "interval": interval,
                      "startTime": start, "endTime": end}},
        timeout=15,
    )
    r.raise_for_status()
    return [float(c["c"]) for c in r.json()]


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    d = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    g = [x if x > 0 else 0.0 for x in d]
    l = [-x if x < 0 else 0.0 for x in d]
    ag = sum(g[:period]) / period
    al = sum(l[:period]) / period
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + g[i]) / period
        al = (al * (period - 1) + l[i]) / period
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def push(title, msg, tags):
    requests.post(
        f"{NTFY_SERVER}/{NTFY_TOPIC}",
        data=msg.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": tags},
        timeout=10,
    )


def main():
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set — add it as a GitHub Secret.")
        return

    closes = fetch_closes(COIN, INTERVAL)
    if len(closes) < RSI_PERIOD + 3:
        print("Not enough candle data.")
        return

    closed = closes[:-1]                  # drop the still-forming candle
    now  = rsi(closed, RSI_PERIOD)        # RSI at the last closed candle
    prev = rsi(closed[:-1], RSI_PERIOD)   # RSI at the candle before it
    print(f"{COIN} {INTERVAL}  RSI prev={prev:.1f}  now={now:.1f}")

    if prev < UPPER <= now:
        push(f"🔴 {COIN} overbought",
             f"RSI crossed {UPPER} (now {now:.1f}) on {INTERVAL}", "red_circle")
        print("ALERT: overbought")

    if prev > LOWER >= now:
        push(f"🟢 {COIN} oversold",
             f"RSI crossed {LOWER} (now {now:.1f}) on {INTERVAL}", "green_circle")
        print("ALERT: oversold")


if __name__ == "__main__":
    main()
