import yfinance as yf
import pandas as pd
import ta
import numpy as np
import time
import requests
from datetime import datetime
import pytz

# CONFIG

RR=2
MAX_TRADES=3
SCAN_INTERVAL=600
START_CAPITAL=100000
RISK=0.01

IST=pytz.timezone("Asia/Kolkata")

stocks=[
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","TCS.NS","INFY.NS",
"SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","ITC.NS",
"BAJFINANCE.NS","TITAN.NS","ASIANPAINT.NS","MARUTI.NS",
"ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS",
"HAL.NS","BEL.NS","TRENT.NS","POLYCAB.NS","PERSISTENT.NS",
"COFORGE.NS","MPHASIS.NS","SRF.NS","HAVELLS.NS","CUMMINSIND.NS",
"SIEMENS.NS","ABB.NS","APLAPOLLO.NS","DIXON.NS","PAGEIND.NS"
]

# CLEAN DATA

def clean(df):

    if df is None or df.empty:
        return None

    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    for c in ["Open","High","Low","Close","Volume"]:
        if c not in df.columns:
            return None
        df[c]=pd.to_numeric(df[c],errors="coerce")

    df=df.dropna()

    if len(df)<50:
        return None

    return df

# MARKET TREND

def market_trend():

    df=yf.download("^NSEI",period="5d",interval="15m",progress=False)

    df=clean(df)

    close=df["Close"]

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if float(ema20.iloc[-1])>float(ema50.iloc[-1]):
        return "BULL"

    return "BEAR"

# RANK STOCKS

def rank_stock(df,nifty_return):

    close=df["Close"]

    rsi=ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]

    adx=ta.trend.ADXIndicator(
        df["High"],df["Low"],df["Close"],14
    ).adx().iloc[-1]

    returns=close.pct_change().iloc[-1]

    rel_strength=returns-nifty_return

    vol_avg=df["Volume"].rolling(20).mean().iloc[-1]

    if vol_avg==0:
        return None

    rel_vol=df["Volume"].iloc[-1]/vol_avg

    score=rsi+adx+(rel_vol*10)+(rel_strength*100)

    return score

# TRADE SIGNAL

def signal(df,trend):

    close=df["Close"]

    rsi=ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]

    atr=ta.volatility.AverageTrueRange(
        df["High"],df["Low"],df["Close"],14
    ).average_true_range().iloc[-1]

    high=df["High"].rolling(20).max().iloc[-1]

    entry=close.iloc[-1]

    if trend=="BULL" and rsi>55:

        sl=entry-atr
        tp=entry+RR*(entry-sl)

        return ("BUY",entry,sl,tp)

    if trend=="BEAR" and rsi<45:

        sl=entry+atr
        tp=entry-RR*(sl-entry)

        return ("SELL",entry,sl,tp)

    return None

# BACKTEST

def backtest():

    print("\nRunning Quant Backtest\n")

    capital=START_CAPITAL
    trades=0
    wins=0
    losses=0

    trend=market_trend()

    for s in stocks:

        df=yf.download(s,period="45d",interval="15m",progress=False)

        df=clean(df)

        if df is None:
            continue

        for i in range(30,len(df)-5):

            sub=df.iloc[:i]

            sig=signal(sub,trend)

            if not sig:
                continue

            direction,entry,sl,tp=sig

            trades+=1

            future=df.iloc[i:i+5]

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
                capital+=capital*RISK*RR

            else:

                losses+=1
                capital-=capital*RISK

    winrate=(wins/trades*100) if trades else 0
    pf=(wins*RR)/losses if losses else 0

    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("WinRate:",round(winrate,2))
    print("ProfitFactor:",round(pf,2))
    print("FinalCapital:",round(capital,2))

# LIVE SCANNER

def live():

    print("\nInstitutional Quant Scanner Running\n")

    while True:

        trend=market_trend()

        nifty=yf.download("^NSEI",period="2d",interval="15m",progress=False)

        nifty=clean(nifty)

        nifty_return=nifty["Close"].pct_change().iloc[-1]

        ranking=[]

        for s in stocks:

            df=yf.download(s,period="5d",interval="15m",progress=False)

            df=clean(df)

            if df is None:
                continue

            score=rank_stock(df,nifty_return)

            if score:

                ranking.append((s,score))

        ranking=sorted(ranking,key=lambda x:x[1],reverse=True)

        top=ranking[:10]

        trades=[]

        for s,_ in top:

            df=yf.download(s,period="1d",interval="5m",progress=False)

            df=clean(df)

            if df is None:
                continue

            sig=signal(df,trend)

            if sig:

                direction,entry,sl,tp=sig

                trades.append((s,direction,entry,sl,tp))

        trades=trades[:MAX_TRADES]

        for s,d,e,sl,tp in trades:

            print(s,d,e,sl,tp)

        time.sleep(SCAN_INTERVAL)

# START

if __name__=="__main__":

    backtest()

    live()
