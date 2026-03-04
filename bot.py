import yfinance as yf
import pandas as pd
import ta
import requests
import os
import time
from datetime import datetime
import pytz

# ================= CONFIG =================

RR = 2
SCAN_INTERVAL = 600
MAX_TRADES = 3
START_CAPITAL = 100000
RISK = 0.01

BOT_TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

IST=pytz.timezone("Asia/Kolkata")

# ================= STOCK LIST =================

stocks=[
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"SBIN.NS","ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS",
"BAJFINANCE.NS","ASIANPAINT.NS","TITAN.NS","MARUTI.NS",
"ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS",
"ADANIPORTS.NS","DRREDDY.NS","SUNPHARMA.NS","CIPLA.NS",
"DIVISLAB.NS","TMPV.NS","HAL.NS","BEL.NS","TRENT.NS",
"POLYCAB.NS","MPHASIS.NS","COFORGE.NS","PERSISTENT.NS",
"LTIM.NS","SRF.NS","HAVELLS.NS","CUMMINSIND.NS","INDIGO.NS",
"LUPIN.NS","ALKEM.NS","ABB.NS","SIEMENS.NS","APLAPOLLO.NS",
"DIXON.NS","PAGEIND.NS","AARTIIND.NS","PIIND.NS","CHOLAFIN.NS",
"TORNTPHARM.NS","GODREJCP.NS","GODREJPROP.NS","ZYDUSLIFE.NS",
"NMDC.NS","BHEL.NS","IRCTC.NS","TATAPOWER.NS","DLF.NS",
"VEDL.NS","NAUKRI.NS","MUTHOOTFIN.NS","ASTRAL.NS","CONCOR.NS",
"CANBK.NS","BANKBARODA.NS","INDUSTOWER.NS","TVSMOTOR.NS",
"EICHERMOT.NS","HEROMOTOCO.NS","APOLLOHOSP.NS","FORTIS.NS",
"IDFCFIRSTB.NS","BANDHANBNK.NS","ZOMATO.NS"
]

# ================= TELEGRAM =================

def send(msg):

    if BOT_TOKEN and CHAT_ID:

        try:
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})
        except:
            pass


# ================= DATA CLEAN =================

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


# ================= MARKET TREND =================

def market_trend():

    df=yf.download("^NSEI",period="5d",interval="15m",progress=False)

    df=clean(df)

    if df is None:
        return "NONE"

    close=df["Close"]

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if ema20.iloc[-1]>ema50.iloc[-1]:
        return "BULL"

    return "BEAR"


# ================= SIGNAL =================

def signal(df,trend,nifty_return):

    close=df["Close"]

    row=df.iloc[-1]

    returns=close.pct_change().iloc[-1]

    rel_strength=returns-nifty_return

    vol_avg=df["Volume"].rolling(20).mean().iloc[-1]

    if vol_avg==0:
        return None

    rel_vol=row["Volume"]/vol_avg

    rsi=ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]

    adx=ta.trend.ADXIndicator(
        df["High"],df["Low"],df["Close"],14
    ).adx().iloc[-1]

    atr=ta.volatility.AverageTrueRange(
        df["High"],df["Low"],df["Close"],14
    ).average_true_range().iloc[-1]

    if rel_vol<2:
        return None

    if adx<20:
        return None

    if rel_strength<0:
        return None

    entry=row["Close"]

    if trend=="BULL" and rsi>60:

        sl=entry-atr
        tp=entry+RR*(entry-sl)

        score=rsi+adx+rel_vol+rel_strength*100

        return ("BUY",entry,sl,tp,score)

    if trend=="BEAR" and rsi<40:

        sl=entry+atr
        tp=entry-RR*(sl-entry)

        score=rsi+adx+rel_vol+abs(rel_strength)*100

        return ("SELL",entry,sl,tp,score)

    return None


# ================= BACKTEST =================

def backtest():

    print("\nRunning Backtest\n")

    capital=START_CAPITAL
    wins=0
    losses=0
    trades=0

    trend=market_trend()

    for s in stocks:

        df=yf.download(s,period="45d",interval="15m",progress=False)

        df=clean(df)

        if df is None:
            continue

        for i in range(30,len(df)-5):

            sub=df.iloc[:i]

            row=sub.iloc[-1]

            vol_avg=sub["Volume"].rolling(20).mean().iloc[-1]

            if vol_avg==0:
                continue

            rel_vol=row["Volume"]/vol_avg

            if rel_vol<2:
                continue

            atr=ta.volatility.AverageTrueRange(
                sub["High"],sub["Low"],sub["Close"],14
            ).average_true_range().iloc[-1]

            entry=row["Close"]

            if trend=="BULL":

                sl=entry-atr
                tp=entry+RR*(entry-sl)

            else:

                sl=entry+atr
                tp=entry-RR*(sl-entry)

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


# ================= LIVE SCANNER =================

def live():

    print("\nLive Scanner Started\n")

    while True:

        now=datetime.now(IST)

        if now.weekday()>=5:
            time.sleep(60)
            continue

        if now.hour<9 or now.hour>15:
            time.sleep(60)
            continue

        trend=market_trend()

        nifty=yf.download("^NSEI",period="2d",interval="15m",progress=False)

        nifty=clean(nifty)

        if nifty is None:
            continue

        nifty_return=nifty["Close"].pct_change().iloc[-1]

        candidates=[]

        data=yf.download(
            tickers=" ".join(stocks),
            period="5d",
            interval="15m",
            group_by="ticker",
            progress=False
        )

        for s in stocks:

            try:

                df=data[s]

                df=clean(df)

                if df is None:
                    continue

                sig=signal(df,trend,nifty_return)

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


# ================= START =================

if __name__=="__main__":

    backtest()

    live()
