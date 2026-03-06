import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

TELEGRAM_TOKEN="8437837109:AAGMEHO_iqODz2ZQgpYsc-PQ9kiES2Rv06M"
CHAT_ID="1476421832"

NIFTY="^NSEI"

STOPLOSS=0.007
TARGET=0.016


# TELEGRAM
def send_telegram(msg):

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload={
        "chat_id":CHAT_ID,
        "text":msg
    }

    requests.post(url,data=payload)


# NSE STOCK LIST
def load_nse_stocks():

    url="https://archives.nseindia.com/content/equities/EQUITY_L.csv"

    df=pd.read_csv(url)

    stocks=[s+".NS" for s in df["SYMBOL"].tolist()]

    return stocks[:200]


# DATA
def get_data(symbol,period="1d",interval="1m"):

    df=yf.download(symbol,period=period,interval=interval,progress=False)

    df.dropna(inplace=True)

    return df


# VWAP
def add_vwap(df):

    tp=(df.High+df.Low+df.Close)/3

    vwap=(tp*df.Volume).cumsum()/df.Volume.cumsum()

    df["VWAP"]=vwap

    return df


# RELATIVE VOLUME
def add_rel_volume(df):

    avg=df.Volume.rolling(20).mean()

    df["RelVol"]=df.Volume/avg

    return df


# ATR
def add_atr(df):

    high_low=df.High-df.Low
    high_close=np.abs(df.High-df.Close.shift())
    low_close=np.abs(df.Low-df.Close.shift())

    tr=pd.concat([high_low,high_close,low_close],axis=1).max(axis=1)

    df["ATR"]=tr.rolling(14).mean()

    return df


# MARKET BIAS
def market_bias():

    df=get_data(NIFTY)

    df=add_vwap(df)

    last=df.iloc[-1]

    if last.Close>last.VWAP:

        return "BULL"

    return "BEAR"


# LIQUIDITY SWEEP
def liquidity_sweep(df):

    prev_low=df.Low.iloc[-20:-1].min()

    last=df.iloc[-1]

    if last.Low<prev_low and last.Close>prev_low:

        return True

    return False


# BREAKOUT STRENGTH
def breakout_strength(df):

    prev_high=df.High.iloc[-20:-1].max()

    last=df.Close.iloc[-1]

    if last>prev_high:

        return True

    return False


# SCORE STOCK
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

    if liquidity_sweep(df):
        score+=15

    momentum=(last.Close-df.Close.iloc[-10])/df.Close.iloc[-10]

    if momentum>0:
        score+=15

    if last.ATR>df.ATR.mean():
        score+=10

    if breakout_strength(df):
        score+=10

    if bias=="BULL" and last.Close>last.VWAP:
        score+=10

    return score


# GENERATE SIGNAL
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


# LIVE SCANNER
def run_live():

    print("Bot V6 running")

    stocks=load_nse_stocks()

    while True:

        try:

            bias=market_bias()

            trades=[]

            for s in stocks:

                try:

                    result=generate_signal(s,bias)

                    if result:
                        trades.append(result)

                except:
                    pass

            trades=sorted(trades,key=lambda x:x[3],reverse=True)

            top=trades[:3]

            for trade in top:

                symbol,signal,price,score=trade

                sl=price*(1-STOPLOSS) if signal=="BUY" else price*(1+STOPLOSS)

                target=price*(1+TARGET) if signal=="BUY" else price*(1-TARGET)

                msg=f"""
AI INSTITUTIONAL TRADE

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

            time.sleep(60)

        except Exception as e:

            print("Error:",e)

            time.sleep(60)


# BACKTEST
def backtest(symbol):

    df=get_data(symbol,period="60d",interval="5m")

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


# MAIN
if __name__=="__main__":

    mode=input("mode (live/backtest): ")

    if mode=="live":

        run_live()

    else:

        stocks=load_nse_stocks()

        for s in stocks[:20]:

            backtest(s)
