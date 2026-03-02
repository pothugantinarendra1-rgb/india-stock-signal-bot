import yfinance as yf
import pandas as pd
import ta
import requests
import schedule
import time
import os
import pytz
from datetime import datetime

# ============================
# Environment variables
# ============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN or CHAT_ID missing!")
else:
    print("Telegram credentials loaded successfully")

# ============================
# IST Timezone
# ============================
IST = pytz.timezone("Asia/Kolkata")

# ============================
# Stock List
# ============================
stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","HDFCLIFE.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","NESTLEIND.NS","ONGC.NS","POWERGRID.NS","NTPC.NS",
"BPCL.NS","ADANIPORTS.NS","HEROMOTOCO.NS","GRASIM.NS","DIVISLAB.NS",
"APOLLOHOSP.NS","ADANIENT.NS","BEL.NS","CIPLA.NS","DRREDDY.NS",
"EICHERMOT.NS","M&M.NS","TECHM.NS","SUNPHARMA.NS","JSWSTEEL.NS",
"TATAMOTORS.NS","TATACONSUM.NS","TATASTEEL.NS","COALINDIA.NS","SBILIFE.NS"
]

# ============================
# Telegram Function
# ============================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        response = requests.post(url, data=data)
        print("Telegram response:", response.status_code)
    except Exception as e:
        print("Telegram Error:", e)

# ============================
# Market Trend Function
# ============================
def get_market_trend():
    try:
        df = yf.download("^NSEI", period="5d", interval="15m", progress=False)
        if df.empty:
            return "SIDEWAYS"

        df['ema20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
        df['ema50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
        df.dropna(inplace=True)

        latest = df.iloc[-1]

        if latest['ema20'] > latest['ema50']:
            return "BULL"
        elif latest['ema20'] < latest['ema50']:
            return "BEAR"
        else:
            return "SIDEWAYS"

    except Exception as e:
        print("Market Trend Error:", e)
        return "SIDEWAYS"

# ============================
# Signal Check Function
# ============================
def check_signals_batch(stocks, market_trend):

    print("Downloading stock batch data...")

    try:
        all_data = yf.download(
            tickers=" ".join(stocks),
            period="5d",
            interval="15m",
            group_by='ticker',
            threads=True,
            progress=False
        )
    except Exception as e:
        print("Batch Download Failed:", e)
        return

    for stock in stocks:
        try:
            df = all_data[stock]

            if df.empty or len(df) < 50:
                continue

            df['ema20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
            df['ema50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
            df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['atr'] = ta.volatility.AverageTrueRange(
                df['High'], df['Low'], df['Close'], window=14
            ).average_true_range()

            df['vol_avg'] = df['Volume'].rolling(20).mean()
            df.dropna(inplace=True)

            latest = df.iloc[-1]
            previous = df.iloc[-2]

            price = latest['Close']
            atr = latest['atr']
            vol = latest['Volume']
            vol_avg = latest['vol_avg']

            # Liquidity Filter
            if vol < 1.2 * vol_avg:
                continue

            # BUY Condition
            if (
                latest['ema20'] > latest['ema50']
                and previous['ema20'] <= previous['ema50']
                and latest['rsi'] > 55
                and market_trend == "BULL"
            ):
                sl = price - 1.2 * atr
                target = price + 2 * (price - sl)

                msg = f"""📈 BUY SIGNAL
Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
RR: 1:2"""

                send_telegram(msg)

            # SELL Condition
            elif (
                latest['ema20'] < latest['ema50']
                and previous['ema20'] >= previous['ema50']
                and latest['rsi'] < 45
                and market_trend == "BEAR"
            ):
                sl = price + 1.2 * atr
                target = price - 2 * (sl - price)

                msg = f"""📉 SELL SIGNAL
Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
RR: 1:2"""

                send_telegram(msg)

        except Exception as e:
            print(f"Error processing {stock}:", e)

# ============================
# Main Job
# ============================
def job():

    now = datetime.now(IST)
    print("Current IST Time:", now)

    # Skip weekends
    if now.weekday() >= 5:
        print("Weekend - skipping")
        return

    # Market Hours 9:15 to 3:30
    if now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour > 15:
        print("Market closed - skipping")
        return

    print("Market open - checking signals")

    market_trend = get_market_trend()
    print("Market Trend:", market_trend)

    check_signals_batch(stocks, market_trend)

# ============================
# Scheduler
# ============================
print("Bot started and scheduler initiated...")

schedule.every(15).minutes.do(job)

# Run immediately once on startup
job()

while True:
    schedule.run_pending()
    time.sleep(1)
