import yfinance as yf
import pandas as pd
import ta
import requests
import schedule
import time
import os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Full stock list
stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","HDFC.NS","WIPRO.NS","HDFCLIFE.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","NESTLEIND.NS","ONGC.NS","POWERGRID.NS","NTPC.NS",
"BPCL.NS","ADANIPORTS.NS","HEROMOTOCO.NS","GRASIM.NS","DIVISLAB.NS",
"APOLLOHOSP.NS","ADANIENT.NS","BEL.NS","CIPLA.NS","DRREDDY.NS",
"EICHERMOT.NS","M&M.NS","TECHM.NS","SUNPHARMA.NS","JSWSTEEL.NS",
"TATAMOTORS.NS","TATACONSUM.NS","TATASTEEL.NS","COALINDIA.NS","SBILIFE.NS",
"ICICIGI.NS","LTI.NS","BOSCHLTD.NS","DABUR.NS","AMBUJACEM.NS",
"AUROPHARMA.NS","HINDALCO.NS","HINDUNILVR.NS","BANKBARODA.NS","VEDL.NS",
"ADANITRANS.NS","TORNTPHARM.NS","MINDTREE.NS","COLPAL.NS","PIDILITIND.NS"
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except:
        pass

def get_market_trend():
    try:
        df = yf.download("^NSEI", period="5d", interval="15m")
        df['ema20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
        df['ema50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
        latest = df.iloc[-1]
        if latest['ema20'] > latest['ema50']:
            return "BULL"
        elif latest['ema20'] < latest['ema50']:
            return "BEAR"
        else:
            return "SIDEWAYS"
    except:
        return "SIDEWAYS"

def check_signals_batch(stocks, market_trend):
    tickers_str = " ".join(stocks)
    try:
        all_data = yf.download(tickers=tickers_str, period="5d", interval="15m", group_by='ticker', threads=True)
    except:
        print("Batch download failed")
        return

    for stock in stocks:
        try:
            df = all_data[stock]
            if df.empty or len(df) < 50:
                continue

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

            # Buy signal
            if (latest['ema20'] > latest['ema50'] and previous['ema20'] <= previous['ema50'] 
                and latest['rsi'] > 55 and latest['Volume'] > latest['vol_avg'] and market_trend=="BULL"):
                sl = price - 1.2*atr
                target = price + 2*(price - sl)
                msg = f"📈 BUY\n{stock}\nEntry: {round(price,2)}\nSL: {round(sl,2)}\nTarget: {round(target,2)}\nRR:1:2"
                send_telegram(msg)

            # Sell signal
            elif (latest['ema20'] < latest['ema50'] and previous['ema20'] >= previous['ema50'] 
                  and latest['rsi'] < 45 and latest['Volume'] > latest['vol_avg'] and market_trend=="BEAR"):
                sl = price + 1.2*atr
                target = price - 2*(sl - price)
                msg = f"📉 SELL\n{stock}\nEntry: {round(price,2)}\nSL: {round(sl,2)}\nTarget: {round(target,2)}\nRR:1:2"
                send_telegram(msg)

        except Exception as e:
            print(f"Error {stock}: {e}")

def job():
    now = datetime.now()
    if now.weekday()>=5: return  # skip weekends
    if now.hour<9 or (now.hour==9 and now.minute<15) or now.hour>15: return
    market_trend = get_market_trend()
    print(f"Market Trend: {market_trend}")
    check_signals_batch(stocks, market_trend)

schedule.every(15).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
