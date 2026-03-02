import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# ============================
# ENV VARIABLES
# ============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN or CHAT_ID missing!")
else:
    print("Telegram credentials loaded")

# ============================
# TIMEZONE
# ============================
IST = pytz.timezone("Asia/Kolkata")

# ============================
# STOCK UNIVERSE (Add More If Needed)
# ============================
stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","BAJFINANCE.NS","ASIANPAINT.NS",
"MARUTI.NS","TITAN.NS","ULTRACEMCO.NS","ONGC.NS","NTPC.NS",
"BPCL.NS","ADANIPORTS.NS","DIVISLAB.NS","APOLLOHOSP.NS",
"BEL.NS","CIPLA.NS","DRREDDY.NS","EICHERMOT.NS","M&M.NS",
"TECHM.NS","SUNPHARMA.NS","JSWSTEEL.NS","TATAMOTORS.NS",
"TATASTEEL.NS","COALINDIA.NS","HINDALCO.NS","BANKBARODA.NS"
]

# ============================
# STATE MEMORY
# ============================
active_trades = {}
last_scan_candle = None

# ============================
# TELEGRAM FUNCTION
# ============================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=10)
        print("Telegram Sent")
    except Exception as e:
        print("Telegram Error:", e)

# ============================
# HELPER: CHUNK LIST
# ============================
def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# ============================
# MARKET TREND
# ============================
def get_market_trend():
    try:
        df = yf.download("^NSEI", period="5d", interval="15m", progress=False)
        if df.empty:
            return "SIDEWAYS"

        close = df["Close"].squeeze()

        ema20 = ta.trend.EMAIndicator(close, 20).ema_indicator()
        ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()

        if ema20.iloc[-1] > ema50.iloc[-1]:
            return "BULL"
        elif ema20.iloc[-1] < ema50.iloc[-1]:
            return "BEAR"
        else:
            return "SIDEWAYS"

    except Exception as e:
        print("Market Trend Error:", e)
        return "SIDEWAYS"

# ============================
# SIGNAL SCORE
# ============================
def calculate_score(latest, market_trend):
    score = 0

    if latest["ema20"] > latest["ema50"]:
        score += 2

    if latest["rsi"] > 60:
        score += 2

    if latest["Volume"] > 1.5 * latest["vol_avg"]:
        score += 2

    if market_trend == "BULL":
        score += 2

    return score

# ============================
# MAIN SIGNAL ENGINE
# ============================
def check_signals():

    global last_scan_candle

    market_trend = get_market_trend()
    print("Market Trend:", market_trend)

    trade_candidates = []

    for batch in chunk_list(stocks, 8):

        for stock in batch:

            try:
                df = yf.download(stock, period="5d", interval="15m", progress=False)

                if df.empty or len(df) < 60:
                    continue

                # ---- FIXED 1D DATA ISSUE ----
                close = df["Close"].squeeze()
                high = df["High"].squeeze()
                low = df["Low"].squeeze()
                volume = df["Volume"].squeeze()

                df["ema20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
                df["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()
                df["rsi"] = ta.momentum.RSIIndicator(close, 14).rsi()
                df["atr"] = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()
                df["vol_avg"] = volume.rolling(20).mean()

                df.dropna(inplace=True)

                latest = df.iloc[-1]
                previous = df.iloc[-2]
                candle_time = df.index[-1]

                if last_scan_candle == candle_time:
                    continue

                price = latest["Close"]
                atr = latest["atr"]

                # BUY CONDITION
                if (latest["ema20"] > latest["ema50"]
                    and previous["ema20"] <= previous["ema50"]
                    and latest["rsi"] > 55
                    and market_trend == "BULL"):

                    score = calculate_score(latest, market_trend)
                    sl = price - 1.2 * atr
                    target = price + 2 * (price - sl)

                    trade_candidates.append({
                        "stock": stock,
                        "type": "BUY",
                        "price": price,
                        "sl": sl,
                        "target": target,
                        "score": score
                    })

                # SELL CONDITION
                elif (latest["ema20"] < latest["ema50"]
                      and previous["ema20"] >= previous["ema50"]
                      and latest["rsi"] < 45
                      and market_trend == "BEAR"):

                    score = calculate_score(latest, market_trend)
                    sl = price + 1.2 * atr
                    target = price - 2 * (sl - price)

                    trade_candidates.append({
                        "stock": stock,
                        "type": "SELL",
                        "price": price,
                        "sl": sl,
                        "target": target,
                        "score": score
                    })

            except Exception as e:
                print("Error:", stock, e)

        time.sleep(2)

    if trade_candidates:
        trade_candidates = sorted(trade_candidates, key=lambda x: x["score"], reverse=True)
        top_trades = trade_candidates[:3]

        for trade in top_trades:
            active_trades[trade["stock"]] = trade

            send_telegram(
f"""🔥 HIGH QUALITY SIGNAL (Score {trade['score']})

{trade['type']} - {trade['stock']}
Entry: {round(trade['price'],2)}
SL: {round(trade['sl'],2)}
Target: {round(trade['target'],2)}"""
            )

    last_scan_candle = datetime.now(IST)

# ============================
# TRADE MONITOR
# ============================
def monitor_trades():

    for stock in list(active_trades.keys()):

        try:
            df = yf.download(stock, period="1d", interval="5m", progress=False)
            if df.empty:
                continue

            price = df["Close"].iloc[-1]
            trade = active_trades[stock]

            if trade["type"] == "BUY":
                if price <= trade["sl"]:
                    send_telegram(f"❌ SL HIT {stock}")
                    del active_trades[stock]
                elif price >= trade["target"]:
                    send_telegram(f"🎯 TARGET HIT {stock}")
                    del active_trades[stock]

            elif trade["type"] == "SELL":
                if price >= trade["sl"]:
                    send_telegram(f"❌ SL HIT {stock}")
                    del active_trades[stock]
                elif price <= trade["target"]:
                    send_telegram(f"🎯 TARGET HIT {stock}")
                    del active_trades[stock]

        except:
            pass

# ============================
# MAIN LOOP (15m Sync)
# ============================
print("🚀 Professional Intraday Engine Started")

while True:

    now = datetime.now(IST)

    if now.weekday() >= 5:
        time.sleep(60)
        continue

    if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and now.hour < 15:

        if now.minute % 15 == 0 and now.second < 5:
            print("Running 15m Scan at", now)
            check_signals()
            time.sleep(60)

        monitor_trades()

    time.sleep(2)
