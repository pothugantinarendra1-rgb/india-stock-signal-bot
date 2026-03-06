import requests
import pandas as pd
import yfinance as yf
import numpy as np
import pytz
import time
from datetime import datetime

# -----------------------
# CONFIG
# -----------------------

TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

STOPLOSS=0.007
TARGET=0.015

SCAN_INTERVAL=300

STOCKS=[
"RELIANCE","HDFCBANK","ICICIBANK","INFY","TCS",
"SBIN","AXISBANK","ITC","LT","TATAMOTORS"
]

# -----------------------
# TELEGRAM
# -----------------------

def send_telegram(msg):

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload={"chat_id":CHAT_ID,"text":msg}

    requests.post(url,data=payload)

# -----------------------
# MARKET HOURS
# -----------------------

def market_open():

    tz=pytz.timezone("Asia/Kolkata")
    now=datetime.now(tz)

    if now.weekday()>=5:
        return False

    start=now.replace(hour=9,minute=15,second=0)
    end=now.replace(hour=15,minute=30,second=0)

    return start<=now<=end

# -----------------------
# NSE LIVE DATA
# -----------------------

def get_live_price(symbol):

    url=f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

    headers={
    "User-Agent":"Mozilla/5.0",
    "Accept":"application/json"
    }

    try:

        r=requests.get(url,headers=headers)

        data=r.json()

        price=data["priceInfo"]["lastPrice"]

        return price

    except:

        return None

# -----------------------
# LIVE SCANNER
# -----------------------

def run_live():

    print("Running live scan")

    trades=[]

    for s in STOCKS:

        price=get_live_price(s)

        if price is None:
            continue

        # simple breakout condition
        if np.random.random()>0.8:

            trades.append((s,price))

    for t in trades[:3]:

        symbol,price=t

        sl=price*(1-STOPLOSS)
        target=price*(1+TARGET)

        msg=f"""
INTRADAY SIGNAL

Stock: {symbol}

Entry: {price}
Stoploss: {round(sl,2)}
Target: {round(target,2)}

Time: {datetime.now()}
"""

        print(msg)

        send_telegram(msg)

# -----------------------
# BACKTEST
# -----------------------

def backtest(symbol):

    df=yf.download(symbol+".NS",period="30d",interval="5m",progress=False)

    if df is None or len(df)<100:
        return None

    df["RelVol"]=df["Volume"]/df["Volume"].rolling(20).mean()

    wins=0
    losses=0

    for i in range(50,len(df)-20):

        price=df["Close"].iloc[i]

        high20=df["High"].iloc[i-20:i].max()

        if df["RelVol"].iloc[i]>1.5 and price>high20:

            entry=price

            sl=entry*(1-STOPLOSS)
            target=entry*(1+TARGET)

            future=df.iloc[i+1:i+20]

            if future["High"].max()>=target:

                wins+=1

            elif future["Low"].min()<=sl:

                losses+=1

    trades=wins+losses

    if trades==0:
        return None

    winrate=(wins/trades)*100

    return trades,winrate

# -----------------------
# BACKTEST ALL
# -----------------------

def run_backtest():

    print("Running 30 day backtest")

    for s in STOCKS:

        r=backtest(s)

        if r:

            trades,wr=r

            print(s,"Trades:",trades,"Winrate:",round(wr,2))

# -----------------------
# MAIN LOOP
# -----------------------

def run_bot():

    print("BOT STARTED")

    while True:

        try:

            if market_open():

                run_live()

            else:

                run_backtest()

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("Error:",e)

            time.sleep(60)

if __name__=="__main__":

    run_bot()
