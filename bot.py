import yfinance as yf
import pandas as pd
import requests
import numpy as np
import time
from datetime import datetime
import pytz

IST=pytz.timezone("Asia/Kolkata")

RR=2
MAX_TRADES=3
SCAN_INTERVAL=600

stocks=[
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","TCS.NS","INFY.NS",
"SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","ITC.NS",
"BAJFINANCE.NS","TITAN.NS","ASIANPAINT.NS","MARUTI.NS",
"HAL.NS","BEL.NS","TRENT.NS","POLYCAB.NS","PERSISTENT.NS",
"COFORGE.NS","MPHASIS.NS","SRF.NS","HAVELLS.NS","CUMMINSIND.NS",
"SIEMENS.NS","ABB.NS","APLAPOLLO.NS","DIXON.NS","PAGEIND.NS"
]

# ================= MARKET BIAS =================

def market_bias():

    df=yf.download("^NSEI",period="5d",interval="15m")

    close=df["Close"]

    vwap=(close*df["Volume"]).cumsum()/df["Volume"].cumsum()

    if close.iloc[-1]>vwap.iloc[-1]:

        return "BULL"

    return "BEAR"

# ================= FVG DETECTION =================

def find_fvg(df):

    gaps=[]

    for i in range(2,len(df)):

        c1=df.iloc[i-2]
        c3=df.iloc[i]

        if c1["High"]<c3["Low"]:

            gaps.append(("bull",c1["High"],c3["Low"]))

        if c1["Low"]>c3["High"]:

            gaps.append(("bear",c3["High"],c1["Low"]))

    return gaps

# ================= LIQUIDITY SWEEP =================

def liquidity_sweep(df):

    prev_high=df["High"].rolling(20).max().iloc[-2]

    prev_low=df["Low"].rolling(20).min().iloc[-2]

    last=df.iloc[-1]

    if last["Low"]<prev_low:

        return "sell_liquidity"

    if last["High"]>prev_high:

        return "buy_liquidity"

    return None

# ================= SIGNAL =================

def signal(df,bias):

    sweep=liquidity_sweep(df)

    gaps=find_fvg(df)

    if not gaps:
        return None

    last=df.iloc[-1]

    for g in gaps[-3:]:

        direction,low,high=g

        if direction=="bull" and bias=="BULL":

            if low<last["Close"]<high:

                sl=last["Low"]

                entry=last["Close"]

                tp=entry+RR*(entry-sl)

                return ("BUY",entry,sl,tp)

        if direction=="bear" and bias=="BEAR":

            if low<last["Close"]<high:

                sl=last["High"]

                entry=last["Close"]

                tp=entry-RR*(sl-entry)

                return ("SELL",entry,sl,tp)

    return None

# ================= BACKTEST =================

def backtest():

    trades=0
    wins=0
    losses=0

    bias=market_bias()

    for s in stocks:

        df=yf.download(s,period="45d",interval="15m")

        if df.empty:
            continue

        for i in range(30,len(df)-5):

            sub=df.iloc[:i]

            sig=signal(sub,bias)

            if not sig:
                continue

            direction,entry,sl,tp=sig

            future=df.iloc[i:i+5]

            trades+=1

            result="SL"

            for _,f in future.iterrows():

                if direction=="BUY":

                    if f["Low"]<=sl:
                        break

                    if f["High"]>=tp:
                        result="TP"
                        break

                if direction=="SELL":

                    if f["High"]>=sl:
                        break

                    if f["Low"]<=tp:
                        result="TP"
                        break

            if result=="TP":
                wins+=1
            else:
                losses+=1

    winrate=(wins/trades*100) if trades else 0

    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("WinRate:",round(winrate,2))

# ================= LIVE SCANNER =================

def live():

    print("Smart Money Scanner Running")

    while True:

        bias=market_bias()

        signals=[]

        for s in stocks:

            df=yf.download(s,period="1d",interval="5m")

            if df.empty:
                continue

            sig=signal(df,bias)

            if sig:

                direction,entry,sl,tp=sig

                signals.append((s,direction,entry,sl,tp))

        signals=signals[:MAX_TRADES]

        for s,d,e,sl,tp in signals:

            print(s,d,e,sl,tp)

        time.sleep(SCAN_INTERVAL)

# ================= START =================

if __name__=="__main__":

    backtest()

    live()
