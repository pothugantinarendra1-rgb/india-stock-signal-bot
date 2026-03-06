import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import pytz
from datetime import datetime

TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

STOPLOSS=0.007
TARGET=0.016

SCAN_INTERVAL=180

NIFTY="^NSEI"

# Sector leaders
SECTOR_STOCKS={
"IT":["INFY.NS","TCS.NS","HCLTECH.NS"],
"BANK":["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS"],
"ENERGY":["RELIANCE.NS","ONGC.NS"],
"METAL":["TATASTEEL.NS","JSWSTEEL.NS"],
"FMCG":["ITC.NS","HINDUNILVR.NS"]
}

STOCKS=[s for sector in SECTOR_STOCKS.values() for s in sector]

last_signals={}

# -----------------------
# TELEGRAM
# -----------------------

def send_telegram(msg):

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload={
        "chat_id":CHAT_ID,
        "text":msg
    }

    requests.post(url,data=payload)

# -----------------------
# MARKET HOURS
# -----------------------

def market_open():

    india=pytz.timezone("Asia/Kolkata")

    now=datetime.now(india)

    if now.weekday()>=5:
        return False

    start=now.replace(hour=9,minute=15,second=0)
    end=now.replace(hour=15,minute=30,second=0)

    return start<=now<=end

# -----------------------
# DATA DOWNLOAD
# -----------------------

def download_data():

    tickers=STOCKS+[NIFTY]

    data=yf.download(
        tickers,
        period="1d",
        interval="1m",
        group_by="ticker",
        progress=False,
        threads=False
    )

    return data

# -----------------------
# INDICATORS
# -----------------------

def add_vwap(df):

    tp=(df["High"]+df["Low"]+df["Close"])/3

    df["VWAP"]=(tp*df["Volume"]).cumsum()/df["Volume"].cumsum()

    return df

def add_rel_volume(df):

    avg=df["Volume"].rolling(20).mean()

    df["RelVol"]=df["Volume"]/avg

    return df

def add_atr(df):

    high_low=df["High"]-df["Low"]
    high_close=np.abs(df["High"]-df["Close"].shift())
    low_close=np.abs(df["Low"]-df["Close"].shift())

    tr=pd.concat([high_low,high_close,low_close],axis=1).max(axis=1)

    df["ATR"]=tr.rolling(14).mean()

    return df

# -----------------------
# MARKET TREND
# -----------------------

def market_bias(df):

    df=add_vwap(df)

    price=float(df["Close"].iloc[-1])
    vwap=float(df["VWAP"].iloc[-1])

    if price>vwap:
        return "BULL"

    return "BEAR"

# -----------------------
# SCORE
# -----------------------

def score_stock(df,bias):

    df=add_vwap(df)
    df=add_rel_volume(df)
    df=add_atr(df)

    price=float(df["Close"].iloc[-1])
    vwap=float(df["VWAP"].iloc[-1])

    score=0

    if price>vwap:
        score+=20

    rel_vol=float(df["RelVol"].iloc[-1])

    if rel_vol>2:
        score+=20

    prev_high=float(df["High"].iloc[-20:-1].max())

    if price>prev_high:
        score+=20

    momentum=(price-df["Close"].iloc[-10])/df["Close"].iloc[-10]

    if momentum>0:
        score+=15

    atr=float(df["ATR"].iloc[-1])

    if atr>df["ATR"].mean():
        score+=15

    if bias=="BULL":
        score+=10

    return score

# -----------------------
# LIVE SCAN
# -----------------------

def run_live():

    data=download_data()

    nifty=data[NIFTY]

    bias=market_bias(nifty)

    trades=[]

    for symbol in STOCKS:

        try:

            df=data[symbol].dropna()

            if len(df)<40:
                continue

            score=score_stock(df,bias)

            if score<65:
                continue

            price=float(df["Close"].iloc[-1])
            vwap=float(df["VWAP"].iloc[-1])

            if price>vwap and bias=="BULL":

                signal="BUY"

            elif price<vwap and bias=="BEAR":

                signal="SELL"

            else:
                continue

            if symbol in last_signals:
                continue

            trades.append((symbol,signal,price,score))

            last_signals[symbol]=True

        except:
            continue

    trades=sorted(trades,key=lambda x:x[3],reverse=True)

    top=trades[:5]

    for trade in top:

        symbol,signal,price,score=trade

        sl=price*(1-STOPLOSS) if signal=="BUY" else price*(1+STOPLOSS)
        target=price*(1+TARGET) if signal=="BUY" else price*(1-TARGET)

        msg=f"""
INSTITUTIONAL TRADE

Stock: {symbol}
Signal: {signal}
Score: {score}

Entry: {round(price,2)}
Stoploss: {round(sl,2)}
Target: {round(target,2)}

Time: {datetime.now()}
"""

        send_telegram(msg)

        print(msg)

# -----------------------
# BOT LOOP
# -----------------------

def run_bot():

    print("BOT V8 STARTED")

    while True:

        try:

            if market_open():

                print("LIVE SCAN")

                run_live()

            else:

                print("Market closed")

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("Error:",e)

            time.sleep(60)

if __name__=="__main__":

    run_bot()
