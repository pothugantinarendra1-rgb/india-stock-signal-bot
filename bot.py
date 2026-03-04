import yfinance as yf
import pandas as pd
import ta
import requests
import os
import time
import pytz
from datetime import datetime

# =========================
# CONFIG
# =========================

RR = 2
SCAN_INTERVAL = 900
START_CAPITAL = 100000
RISK_PER_TRADE = 0.01

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

# =========================
# NSE LARGE + MIDCAP LIST
# =========================

stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"SBIN.NS","ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS",
"BAJFINANCE.NS","ASIANPAINT.NS","TITAN.NS","MARUTI.NS",
"ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS",
"ADANIPORTS.NS","DRREDDY.NS","SUNPHARMA.NS","CIPLA.NS",
"DIVISLAB.NS","SBILIFE.NS","HDFCLIFE.NS","TATAMOTORS.NS",
"HAL.NS","BEL.NS","TRENT.NS","POLYCAB.NS","SRF.NS",
"MPHASIS.NS","COFORGE.NS","PERSISTENT.NS","LTIM.NS",
"VOLTAS.NS","HAVELLS.NS","CUMMINSIND.NS","INDIGO.NS",
"AUROPHARMA.NS","LUPIN.NS","ALKEM.NS","TORNTPHARM.NS"
]

# =========================
# TELEGRAM
# =========================

def send(msg):

    if BOT_TOKEN and CHAT_ID:

        try:

            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})

        except:

            pass


# =========================
# DOWNLOAD DATA
# =========================

def get_data(symbol,period="60d",interval="15m"):

    df=yf.download(symbol,period=period,interval=interval,progress=False)

    if df.empty:
        return None

    df.columns=[c for c in df.columns]

    df["Close"]=pd.to_numeric(df["Close"],errors="coerce")
    df["High"]=pd.to_numeric(df["High"],errors="coerce")
    df["Low"]=pd.to_numeric(df["Low"],errors="coerce")
    df["Volume"]=pd.to_numeric(df["Volume"],errors="coerce")

    df.dropna(inplace=True)

    return df


# =========================
# INDICATORS
# =========================

def add_indicators(df):

    close=df["Close"]
    high=df["High"]
    low=df["Low"]

    df["ema20"]=ta.trend.EMAIndicator(close,20).ema_indicator()
    df["ema50"]=ta.trend.EMAIndicator(close,50).ema_indicator()

    df["rsi"]=ta.momentum.RSIIndicator(close,14).rsi()

    df["adx"]=ta.trend.ADXIndicator(high,low,close,14).adx()

    df["atr"]=ta.volatility.AverageTrueRange(high,low,close,14).average_true_range()

    df["vwap"]=ta.volume.VolumeWeightedAveragePrice(
        high,low,close,df["Volume"]
    ).volume_weighted_average_price()

    df["vol_avg"]=df["Volume"].rolling(20).mean()
    df["rel_vol"]=df["Volume"]/df["vol_avg"]

    df.dropna(inplace=True)

    return df


# =========================
# MARKET TREND
# =========================

def market_trend():

    df=get_data("^NSEI","60d","60m")

    if df is None:
        return "NONE"

    df=add_indicators(df)

    if df["ema20"].iloc[-1]>df["ema50"].iloc[-1]:

        return "BULL"

    return "BEAR"


# =========================
# SIGNAL LOGIC
# =========================

def signal(row,trend):

    if row["rel_vol"]<1.5:
        return None

    if row["adx"]<20:
        return None

    if trend=="BULL":

        if row["Close"]>row["vwap"] and row["rsi"]>60 and row["ema20"]>row["ema50"]:

            return "BUY"

    if trend=="BEAR":

        if row["Close"]<row["vwap"] and row["rsi"]<40 and row["ema20"]<row["ema50"]:

            return "SELL"

    return None


# =========================
# BACKTEST ENGINE
# =========================

def backtest():

    print("\nRunning Backtest...\n")

    capital=START_CAPITAL
    wins=0
    losses=0
    trades=0

    trend=market_trend()

    for stock in stocks:

        df=get_data(stock,"45d","15m")

        if df is None:
            continue

        df=add_indicators(df)

        for i in range(len(df)-10):

            row=df.iloc[i]

            direction=signal(row,trend)

            if direction is None:
                continue

            trades+=1

            entry=row["Close"]
            atr=row["atr"]

            if direction=="BUY":

                sl=entry-1.5*atr
                target=entry+RR*(entry-sl)

            else:

                sl=entry+1.5*atr
                target=entry-RR*(sl-entry)

            future=df.iloc[i+1:i+10]

            result="SL"

            for _,f in future.iterrows():

                if direction=="BUY":

                    if f["Low"]<=sl:
                        break

                    if f["High"]>=target:

                        result="TP"
                        break

                else:

                    if f["High"]>=sl:
                        break

                    if f["Low"]<=target:

                        result="TP"
                        break

            if result=="TP":

                wins+=1
                capital+=capital*RISK_PER_TRADE*RR

            else:

                losses+=1
                capital-=capital*RISK_PER_TRADE

    winrate=(wins/trades*100) if trades else 0
    pf=(wins*RR)/losses if losses else 0

    print("Backtest Results\n")
    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("Win Rate:",round(winrate,2),"%")
    print("Profit Factor:",round(pf,2))
    print("Final Capital:",round(capital,2))


# =========================
# LIVE SCANNER
# =========================

def live():

    print("\nLive Scanner Started\n")

    while True:

        now=datetime.now(IST)

        if now.weekday()>=5:

            time.sleep(60)
            continue

        if not (9<=now.hour<=15):

            time.sleep(60)
            continue

        trend=market_trend()

        candidates=[]

        for stock in stocks:

            df=get_data(stock,"5d","15m")

            if df is None:
                continue

            df=add_indicators(df)

            row=df.iloc[-1]

            direction=signal(row,trend)

            if direction:

                score=row["rsi"]+row["adx"]

                candidates.append((stock,direction,row,score))

        candidates.sort(key=lambda x:x[3],reverse=True)

        candidates=candidates[:3]

        for s in candidates:

            stock,dir,row,_=s

            entry=row["Close"]
            atr=row["atr"]

            if dir=="BUY":

                sl=entry-1.5*atr
                target=entry+RR*(entry-sl)

            else:

                sl=entry+1.5*atr
                target=entry-RR*(sl-entry)

            msg=f"""
{dir} {stock}

Entry: {round(entry,2)}
Stop Loss: {round(sl,2)}
Target: {round(target,2)}
RR: 1:{RR}
"""

            print(msg)

            send(msg)

        time.sleep(SCAN_INTERVAL)


# =========================
# START BOT
# =========================

if __name__=="__main__":

    backtest()

    live()
