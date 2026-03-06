import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

NIFTY="^NSEI"

STOPLOSS=0.007
TARGET=0.016

SCAN_INTERVAL=180

# top liquid stocks
STOCKS=[
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
"SBIN.NS","AXISBANK.NS","ITC.NS","LT.NS","TATAMOTORS.NS",
"BAJFINANCE.NS","HCLTECH.NS","ASIANPAINT.NS","MARUTI.NS",
"KOTAKBANK.NS","SUNPHARMA.NS","ULTRACEMCO.NS","NTPC.NS",
"TITAN.NS","POWERGRID.NS","ONGC.NS","ADANIENT.NS","ADANIPORTS.NS",
"COALINDIA.NS","HINDALCO.NS","JSWSTEEL.NS","GRASIM.NS",
"TATASTEEL.NS","BAJAJFINSV.NS","INDUSINDBK.NS"
]

last_signals={}

# =========================
# TELEGRAM
# =========================

def send_telegram(msg):

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload={
        "chat_id":CHAT_ID,
        "text":msg
    }

    requests.post(url,data=payload)


# =========================
# DATA
# =========================

def get_data(symbol):

    df=yf.download(symbol,period="1d",interval="1m",progress=False)

    df.dropna(inplace=True)

    return df


# =========================
# INDICATORS
# =========================

def add_vwap(df):

    tp=(df.High+df.Low+df.Close)/3

    df["VWAP"]=(tp*df.Volume).cumsum()/df.Volume.cumsum()

    return df


def add_rel_volume(df):

    avg=df.Volume.rolling(20).mean()

    df["RelVol"]=df.Volume/avg

    return df


def add_atr(df):

    high_low=df.High-df.Low
    high_close=np.abs(df.High-df.Close.shift())
    low_close=np.abs(df.Low-df.Close.shift())

    tr=pd.concat([high_low,high_close,low_close],axis=1).max(axis=1)

    df["ATR"]=tr.rolling(14).mean()

    return df


# =========================
# MARKET TREND
# =========================

def market_bias():

    df=get_data(NIFTY)

    df=add_vwap(df)

    last=df.iloc[-1]

    if last.Close>last.VWAP:
        return "BULL"

    return "BEAR"


# =========================
# SCORE STOCK
# =========================

def score_stock(df,bias):

    df=add_vwap(df)
    df=add_rel_volume(df)
    df=add_atr(df)

    last=df.iloc[-1]

    score=0

    if last.Close>last.VWAP:
        score+=20

    if last.RelVol>1.8:
        score+=20

    prev_high=df.High.iloc[-20:-1].max()

    if last.Close>prev_high:
        score+=20

    momentum=(last.Close-df.Close.iloc[-10])/df.Close.iloc[-10]

    if momentum>0:
        score+=15

    if last.ATR>df.ATR.mean():
        score+=15

    if bias=="BULL":
        score+=10

    return score


# =========================
# SIGNAL
# =========================

def generate_signal(symbol,bias):

    df=get_data(symbol)

    if len(df)<40:
        return None

    score=score_stock(df,bias)

    if score<70:
        return None

    price=df.Close.iloc[-1]

    if price>df.VWAP.iloc[-1] and bias=="BULL":
        signal="BUY"

    elif price<df.VWAP.iloc[-1] and bias=="BEAR":
        signal="SELL"

    else:
        return None

    return symbol,signal,price,score


# =========================
# SCANNER
# =========================

def run_live():

    print("BOT STARTED")

    while True:

        try:

            bias=market_bias()

            trades=[]

            for s in STOCKS:

                try:

                    result=generate_signal(s,bias)

                    if result:

                        symbol,signal,price,score=result

                        if symbol in last_signals:
                            continue

                        trades.append(result)

                        last_signals[symbol]=True

                except:
                    pass

            trades=sorted(trades,key=lambda x:x[3],reverse=True)

            top=trades[:3]

            for trade in top:

                symbol,signal,price,score=trade

                sl=price*(1-STOPLOSS) if signal=="BUY" else price*(1+STOPLOSS)

                target=price*(1+TARGET) if signal=="BUY" else price*(1-TARGET)

                msg=f"""
INTRADAY AI SIGNAL

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

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("Error:",e)

            time.sleep(60)


# =========================
# BACKTEST
# =========================

def backtest(symbol):

    df=yf.download(symbol,period="60d",interval="5m",progress=False)

    df=add_vwap(df)
    df=add_rel_volume(df)
    df=add_atr(df)

    wins=0
    losses=0

    for i in range(50,len(df)-20):

        row=df.iloc[i]

        score=score_stock(df.iloc[:i],"BULL")

        if score<70:
            continue

        entry=row.Close

        sl=entry*(1-STOPLOSS)
        target=entry*(1+TARGET)

        future=df.iloc[i+1:i+20]

        if future.High.max()>=target:
            wins+=1
        elif future.Low.min()<=sl:
            losses+=1

    total=wins+losses

    if total>0:
        winrate=(wins/total)*100
    else:
        winrate=0

    print(symbol,"Winrate:",round(winrate,2),"%","Trades:",total)


# =========================
# START BOT
# =========================

if __name__=="__main__":

    run_live()
