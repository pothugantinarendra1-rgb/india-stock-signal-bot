import yfinance as yf
import pandas as pd
import numpy as np
import requests
import pytz
import time
from datetime import datetime

TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

STOPLOSS=0.007
TARGET=0.015

NIFTY="^NSEI"

STOCKS=[
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
"SBIN.NS","AXISBANK.NS","ITC.NS","LT.NS","TATAMOTORS.NS"
]

SCAN_INTERVAL=300

# -------------------------
# TELEGRAM
# -------------------------

def send_telegram(msg):

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload={
        "chat_id":CHAT_ID,
        "text":msg
    }

    requests.post(url,data=payload)

# -------------------------
# MARKET HOURS
# -------------------------

def market_open():

    tz=pytz.timezone("Asia/Kolkata")
    now=datetime.now(tz)

    if now.weekday()>=5:
        return False

    start=now.replace(hour=9,minute=15,second=0)
    end=now.replace(hour=15,minute=30,second=0)

    return start<=now<=end

# -------------------------
# DATA
# -------------------------

def load_data(symbol,period="1d",interval="1m"):

    try:

        df=yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False
        )

        df=df.dropna()

        if len(df)<50:
            return None

        return df

    except:

        return None

# -------------------------
# INDICATORS
# -------------------------

def indicators(df):

    tp=(df["High"]+df["Low"]+df["Close"])/3
    df["VWAP"]=(tp*df["Volume"]).cumsum()/df["Volume"].cumsum()

    df["RelVol"]=df["Volume"]/df["Volume"].rolling(20).mean()

    df["Momentum"]=df["Close"].pct_change(10)

    return df

# -------------------------
# MARKET TREND
# -------------------------

def market_bias():

    df=load_data(NIFTY)

    if df is None:
        return "NEUTRAL"

    df=indicators(df)

    price=df["Close"].iloc[-1]
    vwap=df["VWAP"].iloc[-1]

    if price>vwap:
        return "BULL"

    return "BEAR"

# -------------------------
# SIGNAL
# -------------------------

def check_signal(symbol,bias):

    df=load_data(symbol)

    if df is None:
        return None

    df=indicators(df)

    price=df["Close"].iloc[-1]
    vwap=df["VWAP"].iloc[-1]
    relvol=df["RelVol"].iloc[-1]

    high20=df["High"].iloc[-20:].max()

    if relvol>1.8 and price>high20 and bias=="BULL":

        return ("BUY",price)

    if relvol>1.8 and price<df["Low"].iloc[-20:].min() and bias=="BEAR":

        return ("SELL",price)

    return None

# -------------------------
# LIVE SCANNER
# -------------------------

def run_live():

    print("Running live scanner")

    bias=market_bias()

    trades=[]

    for s in STOCKS:

        result=check_signal(s,bias)

        if result:

            signal,price=result

            trades.append((s,signal,price))

    for trade in trades[:3]:

        symbol,signal,price=trade

        sl=price*(1-STOPLOSS) if signal=="BUY" else price*(1+STOPLOSS)
        target=price*(1+TARGET) if signal=="BUY" else price*(1-TARGET)

        msg=f"""
INTRADAY SIGNAL

Stock: {symbol}
Signal: {signal}

Entry: {round(price,2)}
Stoploss: {round(sl,2)}
Target: {round(target,2)}

Time: {datetime.now()}
"""

        print(msg)

        send_telegram(msg)

# -------------------------
# BACKTEST
# -------------------------

def backtest(symbol):

    df=load_data(symbol,"30d","5m")

    if df is None:
        return None

    df=indicators(df)

    wins=0
    losses=0

    for i in range(50,len(df)-20):

        price=df["Close"].iloc[i]

        if df["RelVol"].iloc[i]>1.8 and price>df["High"].iloc[i-20:i].max():

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

# -------------------------
# BACKTEST ALL
# -------------------------

def run_backtest():

    print("Running 30-day backtest")

    total_trades=0
    total_wins=0

    for s in STOCKS:

        r=backtest(s)

        if r:

            trades,wr=r

            print(s,"Trades:",trades,"Winrate:",round(wr,2))

# -------------------------
# MAIN LOOP
# -------------------------

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
