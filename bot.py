import yfinance as yf
import pandas as pd
import ta
import requests
import schedule
import time
import os
from datetime import datetime

# ============================
# Environment variables
# ============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ============================
# Full Large + Midcap Stocks
# ============================
stocks = [
# Large Cap
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","HDFC.NS","WIPRO.NS","HDFCLIFE.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","NESTLEIND.NS","ONGC.NS","POWERGRID.NS","NTPC.NS",
"BPCL.NS","ADANIPORTS.NS","HEROMOTOCO.NS","GRASIM.NS","DIVISLAB.NS",
# Mid Cap
"APOLLOHOSP.NS","ADANIENT.NS","BEL.NS","CIPLA.NS","DRREDDY.NS",
"EICHERMOT.NS","M&M.NS","TECHM.NS","SUNPHARMA.NS","JSWSTEEL.NS",
"TATAMOTORS.NS","TATACONSUM.NS","TATASTEEL.NS","COALINDIA.NS","SBILIFE.NS",
"ICICIGI.NS","LTI.NS","BOSCHLTD.NS","DABUR.NS","AMBUJACEM.NS",
"AUROPHARMA.NS","HINDALCO.NS","HINDUNILVR.NS","BANKBARODA.NS","VEDL.NS",
"ADANITRANS.NS","TORNTPHARM.NS","MINDTREE.NS","COLPAL.NS","PIDILITIND.NS"
]

# ============================
# Telegram Function
# ============================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram error:", e)

# ============================
# Signal Logic
# ============================
def check_signal(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="15m")
        if df.empty or len(df) < 50:
            return None

        # Indicators
        df['ema20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
        df['ema50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
        df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['atr'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        df['vol_avg'] = df['Volume'].rolling(20).mean()
        df.dropna(inplace=True)

        latest = df.iloc[-1]
        previous = df.iloc[-2]
        price = latest['Close']
        atr = latest['atr']

        # Buy Condition
        if (latest['ema20'] > latest['ema50'] and
            previous['ema20'] <= previous['ema50'] and
            latest['rsi'] > 55 and
            latest['Volume'] > latest['vol_avg']):
            
            sl = price - (1.2 * atr)
            target = price + 2 * (price - sl)
            return f"📈 BUY SIGNAL\nStock: {symbol}\nEntry: {round(price,2)}\nStop Loss: {round(sl,2)}\nTarget: {round(target,2)}\nRR: 1:2"

        # Sell Condition
        if (latest['ema20'] < latest['ema50'] and
            previous['ema20'] >= previous['ema50'] and
            latest['rsi'] < 45 and
            latest['Volume'] > latest['vol_avg']):
            
            sl = price + (1.2 * atr)
            target = price - 2 * (sl - price)
            return f"📉 SELL SIGNAL\nStock: {symbol}\nEntry: {round(price,2)}\nStop Loss: {round(sl,2)}\nTarget: {round(target,2)}\nRR: 1:2"

        return None

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# ============================
# Main Job Function
# ============================
def job():
    now = datetime.now()
    # Only run during NSE market hours (9:15 AM – 3:30 PM)
    if now.weekday() >= 5:  # skip Saturday & Sunday
        return
    if now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour > 15:
        return

    for stock in stocks:
        signal = check_signal(stock)
        if signal:
            send_telegram(signal)
            time.sleep(2)  # prevent Telegram flood

# ============================
# Schedule Job Every 15 Minutes
# ============================
schedule.every(15).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
