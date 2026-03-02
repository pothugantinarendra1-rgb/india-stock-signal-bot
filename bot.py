import yfinance as yf
import ta
import requests
import time
import os
import pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

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

active_trades = {}
last_scan_candle = None


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
        print("Telegram Sent")
    except Exception as e:
        print("Telegram Error:", e)


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def get_market_trend():
    try:
        df = yf.download("^NSEI", period="5d", interval="15m", progress=False)
        if df.empty:
            return "SIDEWAYS"

        close = df["Close"].squeeze()
        ema20 = ta.trend.EMAIndicator(close, 20).ema_indicator()
        ema50 = ta.trend.EMAIndicator(close, 50).ema_indicator()

        if float(ema20.iloc[-1]) > float(ema50.iloc[-1]):
            return "BULL"
        elif float(ema20.iloc[-1]) < float(ema50.iloc[-1]):
            return "BEAR"
        else:
            return "SIDEWAYS"

    except:
        return "SIDEWAYS"


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

                ema20 = float(latest["ema20"])
                ema50 = float(latest["ema50"])
                rsi = float(latest["rsi"])
                atr = float(latest["atr"])
                price = float(latest["Close"])

                if ema20 > ema50 and float(previous["ema20"]) <= float(previous["ema50"]) and rsi > 55 and market_trend == "BULL":

                    sl = price - 1.2 * atr
                    target = price + 2 * (price - sl)

                    trade_candidates.append({
                        "stock": stock,
                        "type": "BUY",
                        "price": price,
                        "sl": sl,
                        "target": target
                    })

                elif ema20 < ema50 and float(previous["ema20"]) >= float(previous["ema50"]) and rsi < 45 and market_trend == "BEAR":

                    sl = price + 1.2 * atr
                    target = price - 2 * (sl - price)

                    trade_candidates.append({
                        "stock": stock,
                        "type": "SELL",
                        "price": price,
                        "sl": sl,
                        "target": target
                    })

            except Exception as e:
                print("Error:", stock, e)

        time.sleep(2)

    for trade in trade_candidates[:3]:
        active_trades[trade["stock"]] = trade
        send_telegram(
f"""🔥 SIGNAL

{trade['type']} - {trade['stock']}
Entry: {round(trade['price'],2)}
SL: {round(trade['sl'],2)}
Target: {round(trade['target'],2)}"""
        )

    last_scan_candle = datetime.now(IST)


print("🚀 Intraday Engine Started")

while True:

    now = datetime.now(IST)

    if now.weekday() >= 5:
        time.sleep(60)
        continue

    if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and now.hour < 15:

        if now.minute % 15 == 0 and now.second < 5:
            print("Running Scan at", now)
            check_signals()
            time.sleep(60)

    time.sleep(2)
