import yfinance as yf
import pandas as pd
import ta
import requests
import os
import time
from datetime import datetime
import pytz

# ===== CONFIG =====

RR = 2
SCAN_INTERVAL = 600
MAX_TRADES = 3

BOT_TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

IST=pytz.timezone("Asia/Kolkata")

stocks=[
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","TCS.NS","INFY.NS",
"SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","ITC.NS",
"BAJFINANCE.NS","TITAN.NS","ASIANPAINT.NS","MARUTI.NS",
"ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS",
"ADANIPORTS.NS","HAL.NS","BEL.NS","TRENT.NS","POLYCAB.NS",
"PERSISTENT.NS","COFORGE.NS","MPHASIS.NS","LTIM.NS",
"SRF.NS","HAVELLS.NS","CUMMINSIND.NS","DIXON.NS",
"ABB.NS","SIEMENS.NS","APLAPOLLO.NS"
]

# ===== TELEGRAM =====

def send(msg):

    if BOT_TOKEN and CHAT_ID:

        try:
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})
        except:
            pass


# ===== DATA CLEAN =====

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

    if len(df)<40:
        return None

    return df


# ===== MARKET TREND =====

def market_trend():

    df=yf.download("^NSEI",period="5d",interval="15m",progress=False)

    df=clean(df)

    close=df["Close"]

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if ema20.iloc[-1]>ema50.iloc[-1]:
        return "BULL"

    return "BEAR"


# ===== VWAP CALC =====

def add_vwap(df):

    tp=(df["High"]+df["Low"]+df["Close"])/3

    df["vwap"]=(tp*df["Volume"]).cumsum()/df["Volume"].cumsum()

    return df


# ===== SIGNAL =====

def signal(df,trend):

    df=add_vwap(df)

    close=df["Close"]
    row=df.iloc[-1]
    prev=df.iloc[-2]

    rsi=ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]

    vol_avg=df["Volume"].rolling(20).mean().iloc[-1]

    if vol_avg==0:
        return None

    rel_vol=row["Volume"]/vol_avg

    if rel_vol<1.5:
        return None

    entry=row["Close"]

    if trend=="BULL":

        if prev["Low"]<=prev["vwap"] and row["Close"]>row["vwap"] and rsi>50:

            sl=prev["Low"]
            tp=entry+RR*(entry-sl)

            score=rsi+rel_vol

            return ("BUY",entry,sl,tp,score)

    if trend=="BEAR":

        if prev["High"]>=prev["vwap"] and row["Close"]<row["vwap"] and rsi<50:

            sl=prev["High"]
            tp=entry-RR*(sl-entry)

            score=rsi+rel_vol

            return ("SELL",entry,sl,tp,score)

    return None


# ===== BACKTEST =====

def backtest():

    print("\nRunning VWAP Backtest\n")

    trades=0
    wins=0
    losses=0

    trend=market_trend()

    for s in stocks:

        df=yf.download(s,period="45d",interval="15m",progress=False)

        df=clean(df)

        if df is None:
            continue

        df=add_vwap(df)

        for i in range(20,len(df)-5):

            row=df.iloc[i]
            prev=df.iloc[i-1]

            vol_avg=df["Volume"].rolling(20).mean().iloc[i]

            if vol_avg==0:
                continue

            rel_vol=row["Volume"]/vol_avg

            if rel_vol<1.5:
                continue

            entry=row["Close"]

            if trend=="BULL" and prev["Low"]<=prev["vwap"] and row["Close"]>row["vwap"]:

                sl=prev["Low"]
                tp=entry+RR*(entry-sl)

            elif trend=="BEAR" and prev["High"]>=prev["vwap"] and row["Close"]<row["vwap"]:

                sl=prev["High"]
                tp=entry-RR*(sl-entry)

            else:
                continue

            trades+=1

            future=df.iloc[i+1:i+6]

            result="SL"

            for _,f in future.iterrows():

                if trend=="BULL":

                    if f["Low"]<=sl:
                        break

                    if f["High"]>=tp:
                        result="TP"
                        break

                else:

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
    pf=(wins*RR)/losses if losses else 0

    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("WinRate:",round(winrate,2))
    print("ProfitFactor:",round(pf,2))


# ===== LIVE SCANNER =====

def live():

    print("\nV13 Institutional VWAP Scanner Running\n")

    while True:

        trend=market_trend()

        candidates=[]

        data=yf.download(
            tickers=" ".join(stocks),
            period="1d",
            interval="5m",
            group_by="ticker",
            progress=False
        )

        for s in stocks:

            try:

                df=data[s]

                df=clean(df)

                if df is None:
                    continue

                sig=signal(df,trend)

                if sig:

                    direction,entry,sl,tp,score=sig

                    candidates.append((s,direction,entry,sl,tp,score))

            except:
                continue

        candidates.sort(key=lambda x:x[5],reverse=True)

        candidates=candidates[:MAX_TRADES]

        for c in candidates:

            s,dir,entry,sl,tp,_=c

            msg=f"""
{dir} {s}

Entry: {round(entry,2)}
StopLoss: {round(sl,2)}
Target: {round(tp,2)}
RR 1:{RR}
"""

            print(msg)

            send(msg)

        time.sleep(SCAN_INTERVAL)


# ===== START =====

if __name__=="__main__":

    backtest()

    live()
