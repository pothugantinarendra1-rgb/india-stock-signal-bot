import yfinance as yf
import pandas as pd
import ta
import requests
import os
import time
from datetime import datetime
import pytz

# ================= CONFIG =================

SCAN_INTERVAL = 900
RR = 2
START_CAPITAL = 100000
RISK = 0.01

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

# ================= STOCK LIST =================

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

# ================= TELEGRAM =================

def send(msg):
    if BOT_TOKEN and CHAT_ID:
        try:
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})
        except:
            pass


# ================= DATA CLEANER =================

def clean(df):

    if df is None or df.empty:
        return None

    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    required=["Open","High","Low","Close","Volume"]

    for col in required:

        if col not in df.columns:
            return None

        df[col]=pd.to_numeric(df[col],errors="coerce")

    df=df.dropna()

    if len(df)<50:
        return None

    return df


# ================= INDICATORS =================

def indicators(df):

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


# ================= MARKET TREND =================

last_trend_update=0
cached_trend="NONE"

def market_trend():

    global last_trend_update,cached_trend

    if time.time()-last_trend_update<1800:
        return cached_trend

    df=yf.download("^NSEI",period="60d",interval="60m",progress=False)

    df=clean(df)

    if df is None:
        return "NONE"

    close=df["Close"]

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if ema20.iloc[-1]>ema50.iloc[-1]:
        cached_trend="BULL"
    else:
        cached_trend="BEAR"

    last_trend_update=time.time()

    return cached_trend


# ================= SIGNAL =================

def signal(row,trend):

    if row["rel_vol"]<1.5:
        return None

    if row["adx"]<20:
        return None

    if trend=="BULL":

        if row["Close"]>row["vwap"] and row["ema20"]>row["ema50"] and row["rsi"]>60:
            return "BUY"

    if trend=="BEAR":

        if row["Close"]<row["vwap"] and row["ema20"]<row["ema50"] and row["rsi"]<40:
            return "SELL"

    return None


# ================= BACKTEST =================

def backtest():

    print("\nRunning Backtest\n")

    capital=START_CAPITAL
    wins=0
    losses=0
    trades=0

    trend=market_trend()

    data=yf.download(
        tickers=" ".join(stocks),
        period="45d",
        interval="15m",
        group_by="ticker",
        progress=False
    )

    for stock in stocks:

        try:

            df=data[stock]

            df=clean(df)

            if df is None:
                continue

            df=indicators(df)

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
                    tp=entry+RR*(entry-sl)
                else:
                    sl=entry+1.5*atr
                    tp=entry-RR*(sl-entry)

                future=df.iloc[i+1:i+10]

                result="SL"

                for _,f in future.iterrows():

                    if direction=="BUY":

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
                    capital+=capital*RISK*RR
                else:
                    losses+=1
                    capital-=capital*RISK

        except:
            continue

    winrate=(wins/trades*100) if trades else 0
    pf=(wins*RR)/losses if losses else 0

    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("WinRate:",round(winrate,2))
    print("ProfitFactor:",round(pf,2))
    print("FinalCapital:",round(capital,2))


# ================= LIVE SCANNER =================

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

        data=yf.download(
            tickers=" ".join(stocks),
            period="5d",
            interval="15m",
            group_by="ticker",
            progress=False
        )

        candidates=[]

        for stock in stocks:

            try:

                df=data[stock]

                df=clean(df)

                if df is None:
                    continue

                df=indicators(df)

                row=df.iloc[-1]

                direction=signal(row,trend)

                if direction:

                    score=row["rsi"]+row["adx"]+row["rel_vol"]

                    candidates.append((stock,direction,row,score))

            except:
                continue

        candidates.sort(key=lambda x:x[3],reverse=True)

        candidates=candidates[:3]

        for s in candidates:

            stock,dir,row,_=s

            entry=row["Close"]
            atr=row["atr"]

            if dir=="BUY":
                sl=entry-1.5*atr
                tp=entry+RR*(entry-sl)
            else:
                sl=entry+1.5*atr
                tp=entry-RR*(sl-entry)

            msg=f"""
{dir} {stock}

Entry: {round(entry,2)}
Stop Loss: {round(sl,2)}
Target: {round(tp,2)}
RR: 1:{RR}
"""

            print(msg)

            send(msg)

        time.sleep(SCAN_INTERVAL)


# ================= START =================

if __name__=="__main__":

    backtest()

    live()
