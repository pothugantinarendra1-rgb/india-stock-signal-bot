import yfinance as yf
import pandas as pd
import ta
import requests
import schedule
import time
import os
from datetime import datetime

# Environment variables for security
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ===============================
# COMPLETE LARGE + MIDCAP STOCK LIST
# ===============================
stocks = [
# Large Cap Stocks
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","HDFC.NS","WIPRO.NS","HDFCLIFE.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","NESTLEIND.NS","ONGC.NS","POWERGRID.NS","NTPC.NS",
"BPCL.NS","ADANIPORTS.NS","HEROMOTOCO.NS","GRASIM.NS","DIVISLAB.NS",
# Midcap Stocks
"APOLLOHOSP.NS","ADANIENT.NS","BEL.NS","CIPLA.NS","DRREDDY.NS",
"EICHERMOT.NS","M&M.NS","TECHM.NS","SUNPHARMA.NS","JSWSTEEL.NS",
"TATAMOTORS.NS","TATACONSUM.NS","TATASTEEL.NS","COALINDIA.NS","SBILIFE.NS",
"ICICIGI.NS","LTI.NS","BOSCHLTD.NS","DABUR.NS","AMBUJACEM.NS",
"AUROPHARMA.NS","HINDALCO.NS","HINDUNILVR.NS","BANKBARODA.NS","VEDL.NS",
"ADANITRANS.NS","TORNTPHARM.NS","MINDTREE.NS","COLPAL.NS","PIDILITIND.NS"
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot8437837109:AAGMEHO_iqODz2ZQgpYsc-PQ9kiES2Rv06M/sendMessage"
    data = {"chat_id": 1476421832, "text": message}
    requests.post(url, data=data)

def check_signal(symbol):
    df = yf.download(symbol, period="5d", interval="15m")
    if df.empty:
        return None

    # Indicators
    df['ema20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
    df['ema50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(df['Close']).rsi()
    df['atr'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()
    df['vol_avg'] = df['Volume'].rolling(20).mean()
    df.dropna(inplace=True)

    latest = df.iloc[-1]
    previous = df.iloc[-2]
    price = latest['Close']
    atr = latest['atr']

    # BUY Condition
    if latest['ema20'] > latest['ema50'] and previous['ema20'] <= previous['ema50'] and latest['rsi'] > 55 and latest['Volume'] > latest['vol_avg']:
        sl = price - (1.2 * atr)
        target = price + 2*(price - sl)
        return f"📈 BUY\nStock: {symbol}\nEntry: {round(price,2)}\nSL: {round(sl,2)}\nTarget: {round(target,2)}\nRR: 1:2"

    # SELL Condition
    if latest['ema20'] < latest['ema50'] and previous['ema20'] >= previous['ema50'] and latest['rsi'] < 45 and latest['Volume'] > latest['vol_avg']:
        sl = price + (1.2 * atr)
        target = price - 2*(sl - price)
        return f"📉 SELL\nStock: {symbol}\nEntry: {round(price,2)}\nSL: {round(sl,2)}\nTarget: {round(target,2)}\nRR: 1:2"

    return None

def job():
    now = datetime.now()
    if now.hour < 9 or now.hour > 15:
        return  # Market hours only

    for stock in stocks:
        signal = check_signal(stock)
        if signal:
            send_telegram(signal)
            time.sleep(2)  # Avoid Telegram limit

schedule.every(15).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
