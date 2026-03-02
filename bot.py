import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN or CHAT_ID missing!")
else:
    print("Telegram credentials loaded")

# =========================
# TIMEZONE
# =========================
IST = pytz.timezone("Asia/Kolkata")

# =========================
# STOCK LIST (Add More Freely)
# =========================
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

# =========================
# TELEGRAM FUNCTION
# =========================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=10)
        print("Telegram Sent")
    except Exception as e:
        print("Telegram Error:", e)

# =========================
# CHUNK HELPER (Rate Limit Safe)
# =========================
def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# =========================
# MARKET TREND FUNCTION
# =========================
def get_market_trend():
    try:
        df = yf.download("^NSEI", period="5d", interval="15m", progress=False)

        if df.empty:
            return "SIDEWAYS"

        # Handle MultiIndex safely
        if isinstance(df.columns, pd.MultiIndex):
            close = df["Close"].iloc[:, 0]
        else:
            close = df["Close"]

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

# =========================
# SIGNAL ENGINE
# =========================
def check_signals():

    market_trend = get_market_trend()
    print("Market Trend:", market_trend)

    trade_count = 0

    for batch in chunk_list(stocks, 8):

        for stock in batch:

            try:
                df = yf.download(stock, period="5d", interval="15m", progress=False)

                if df.empty or len(df) < 60:
                    continue

                # Handle MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    close = df["Close"].iloc[:, 0]
                    high = df["High"].iloc[:, 0]
                    low = df["Low"].iloc[:, 0]
                    volume = df["Volume"].iloc[:, 0]
                else:
                    close = df["Close"]
                    high = df["High"]
                    low = df["Low"]
                    volume = df["Volume"]

                ema20 = ta.trend.EMAIndicator(close, 20).ema_indicator()
                ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()
                rsi = ta.momentum.RSIIndicator(close, 14).rsi()
                atr = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()

                if len(ema20) < 2:
                    continue

                ema20_now = ema20.iloc[-1]
                ema50_now = ema50.iloc[-1]
                ema20_prev = ema20.iloc[-2]
                ema50_prev = ema50.iloc[-2]
                rsi_now = rsi.iloc[-1]
                atr_now = atr.iloc[-1]
                price = close.iloc[-1]

                # BUY CONDITION
                if (ema20_now > ema50_now and
                    ema20_prev <= ema50_prev and
                    rsi_now > 55 and
                    market_trend == "BULL"):

                    sl = price - 1.2 * atr_now
                    target = price + 2 * (price - sl)

                    send_telegram(
f"""📈 BUY SIGNAL

Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}"""
                    )

                    trade_count += 1

                # SELL CONDITION
                elif (ema20_now < ema50_now and
                      ema20_prev >= ema50_prev and
                      rsi_now < 45 and
                      market_trend == "BEAR"):

                    sl = price + 1.2 * atr_now
                    target = price - 2 * (sl - price)

                    send_telegram(
f"""📉 SELL SIGNAL

Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}"""
                    )

                    trade_count += 1

                if trade_count >= 3:
                    return

            except Exception as e:
                print("Error:", stock, e)

        time.sleep(2)

# =========================
# MAIN LOOP (15M SYNC)
# =========================
print("🚀 Intraday Trading Bot Started")

while True:

    now = datetime.now(IST)

    # Skip weekends
    if now.weekday() >= 5:
        time.sleep(60)
        continue

    # Market hours 9:15 to 3:30
    if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and now.hour < 15:

        # Run exactly at candle close
        if now.minute % 15 == 0 and now.second < 5:
            print("Running 15m Scan at", now)
            check_signals()
            time.sleep(60)

    time.sleep(2)
