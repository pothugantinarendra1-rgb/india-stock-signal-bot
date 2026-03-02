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

# ============================
# TIMEZONE
# ============================
IST = pytz.timezone("Asia/Kolkata")

# ============================
# STOCK LIST (Reduced for stability)
# ============================
stocks = [
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS",
"TATAMOTORS.NS","INFY.NS","SBIN.NS",
"LT.NS","ITC.NS","AXISBANK.NS"
]

# Track active trades
active_trades = {}

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
# MARKET TREND
# ============================
def get_market_trend():
    try:
        df = yf.download("^NSEI", period="5d", interval="15m", progress=False)
        if df.empty:
            return "SIDEWAYS"

        df['ema20'] = ta.trend.EMAIndicator(df['Close'], 20).ema_indicator()
        df['ema50'] = ta.trend.EMAIndicator(df['Close'], 50).ema_indicator()
        df.dropna(inplace=True)

        latest = df.iloc[-1]

        if latest['ema20'] > latest['ema50']:
            return "BULL"
        elif latest['ema20'] < latest['ema50']:
            return "BEAR"
        else:
            return "SIDEWAYS"
    except:
        return "SIDEWAYS"

# ============================
# SIGNAL ENGINE
# ============================
def check_signals():

    market_trend = get_market_trend()
    print("Market Trend:", market_trend)

    for stock in stocks:

        try:
            df = yf.download(stock, period="5d", interval="15m", progress=False)

            if df.empty or len(df) < 60:
                print("No data:", stock)
                continue

            df['ema20'] = ta.trend.EMAIndicator(df['Close'], 20).ema_indicator()
            df['ema50'] = ta.trend.EMAIndicator(df['Close'], 50).ema_indicator()
            df['rsi'] = ta.momentum.RSIIndicator(df['Close'], 14).rsi()
            df['atr'] = ta.volatility.AverageTrueRange(
                df['High'], df['Low'], df['Close'], 14
            ).average_true_range()
            df['vol_avg'] = df['Volume'].rolling(20).mean()

            df.dropna(inplace=True)

            latest = df.iloc[-1]
            previous = df.iloc[-2]

            price = latest['Close']
            atr = latest['atr']
            volume = latest['Volume']
            vol_avg = latest['vol_avg']

            # Volume spike alert
            if volume > 1.5 * vol_avg:
                send_telegram(f"🔔 Volume Spike in {stock}")

            # RSI crossing alerts
            if previous['rsi'] < 30 and latest['rsi'] > 30:
                send_telegram(f"📈 RSI Oversold Bounce {stock}")

            if previous['rsi'] > 70 and latest['rsi'] < 70:
                send_telegram(f"📉 RSI Overbought Drop {stock}")

            # Skip low liquidity
            if volume < 1.2 * vol_avg:
                continue

            # BUY SIGNAL
            if (latest['ema20'] > latest['ema50']
                and previous['ema20'] <= previous['ema50']
                and latest['rsi'] > 55
                and market_trend == "BULL"
                and stock not in active_trades):

                sl = price - 1.2 * atr
                target = price + 2 * (price - sl)

                active_trades[stock] = {
                    "type": "BUY",
                    "sl": sl,
                    "target": target
                }

                send_telegram(
f"""📈 BUY SIGNAL
{stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
RR 1:2"""
                )

            # SELL SIGNAL
            elif (latest['ema20'] < latest['ema50']
                  and previous['ema20'] >= previous['ema50']
                  and latest['rsi'] < 45
                  and market_trend == "BEAR"
                  and stock not in active_trades):

                sl = price + 1.2 * atr
                target = price - 2 * (sl - price)

                active_trades[stock] = {
                    "type": "SELL",
                    "sl": sl,
                    "target": target
                }

                send_telegram(
f"""📉 SELL SIGNAL
{stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
RR 1:2"""
                )

            # ====================
            # TRADE MANAGEMENT
            # ====================
            if stock in active_trades:

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

        except Exception as e:
            print("Error:", stock, e)

# ============================
# EXACT 15-MIN SYNC LOOP
# ============================
print("Advanced Intraday Bot Started...")

while True:

    now = datetime.now(IST)
    minute = now.minute

    # Weekend skip
    if now.weekday() >= 5:
        time.sleep(60)
        continue

    # Market hours 9:15 to 3:30
    if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and now.hour < 15:

        # Run exactly at 15m candle close
        if minute % 15 == 0 and now.second < 5:
            print("Running Signal Check at", now)
            check_signals()
            time.sleep(60)

    time.sleep(1)
