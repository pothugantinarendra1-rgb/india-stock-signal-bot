import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# ================= CONFIG =================

SCAN_INTERVAL = 900
RR_RATIO = 2
RISK = 0.01
START_CAPITAL = 100000

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
"DIVISLAB.NS","HDFCLIFE.NS","SBILIFE.NS","TATAMOTORS.NS",
"HAL.NS","BEL.NS","POLYCAB.NS","TRENT.NS","SRF.NS","PIIND.NS",
"MPHASIS.NS","COFORGE.NS","LTIM.NS","PERSISTENT.NS",
"BALKRISIND.NS","DEEPAKNTR.NS","AUBANK.NS","INDIGO.NS",
"VOLTAS.NS","HAVELLS.NS","CUMMINSIND.NS","TORNTPHARM.NS",
"LUPIN.NS","ALKEM.NS","AUROPHARMA.NS"
]

# ================= TELEGRAM =================

def send(msg):

    if BOT_TOKEN and CHAT_ID:

        try:

            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})

        except:

            pass


# ================= DATA FIX =================

def normalize(df):

    if isinstance(df.columns,pd.MultiIndex):

        df.columns=df.columns.get_level_values(0)

    for col in ["Open","High","Low","Close","Volume"]:

        df[col]=pd.to_numeric(df[col],errors="coerce")

    df=df.dropna()

    return df


# ================= INDICATORS =================

def indicators(df):

    df=normalize(df)

    close=df["Close"]
    high=df["High"]
    low=df["Low"]
    vol=df["Volume"]

    df["ema20"]=ta.trend.EMAIndicator(close,20).ema_indicator()
    df["ema50"]=ta.trend.EMAIndicator(close,50).ema_indicator()

    df["rsi"]=ta.momentum.RSIIndicator(close,14).rsi()

    df["adx"]=ta.trend.ADXIndicator(high,low,close,14).adx()

    df["atr"]=ta.volatility.AverageTrueRange(high,low,close,14).average_true_range()

    df["vol_avg"]=vol.rolling(20).mean()

    df["rel_vol"]=vol/df["vol_avg"]

    df.dropna(inplace=True)

    return df


# ================= MARKET TREND =================

def market_trend():

    df=yf.download("^NSEI",period="60d",interval="60m",progress=False)

    df=normalize(df)

    close=df["Close"]

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if ema20.iloc[-1]>ema50.iloc[-1]:

        return "BULL"

    return "BEAR"


# ================= ENTRY =================

def entry(row,trend):

    if row["rel_vol"]<2:

        return None

    if trend=="BULL":

        if row["ema20"]<=row["ema50"]:
            return None

        if row["Close"]<row["ema20"]:
            return None

        return "BUY"

    else:

        if row["ema20"]>=row["ema50"]:
            return None

        if row["Close"]>row["ema20"]:
            return None

        return "SELL"


# ================= BACKTEST =================

def backtest():

    print("\nRunning Backtest")

    data=yf.download(
        tickers=" ".join(stocks),
        period="60d",
        interval="15m",
        group_by="ticker",
        progress=False
    )

    capital=START_CAPITAL

    trades=0
    wins=0
    losses=0

    trend=market_trend()

    for stock in stocks:

        try:

            df=data[stock]

            df=indicators(df)

            for i in range(len(df)-10):

                row=df.iloc[i]

                direction=entry(row,trend)

                if direction is None:
                    continue

                trades+=1

                entry_price=row["Close"]

                atr=row["atr"]

                if direction=="BUY":

                    sl=entry_price-1.5*atr
                    tp=entry_price+RR_RATIO*(entry_price-sl)

                else:

                    sl=entry_price+1.5*atr
                    tp=entry_price-RR_RATIO*(sl-entry_price)

                future=df.iloc[i+1:i+10]

                result="SL"

                for _,f in future.iterrows():

                    if direction=="BUY":

                        if f["Low"]<=sl: break
                        if f["High"]>=tp:
                            result="TP"
                            break

                    else:

                        if f["High"]>=sl: break
                        if f["Low"]<=tp:
                            result="TP"
                            break

                if result=="TP":

                    wins+=1
                    capital+=capital*RISK*RR_RATIO

                else:

                    losses+=1
                    capital-=capital*RISK

        except:

            continue

    winrate=(wins/trades*100) if trades else 0

    pf=(wins*RR_RATIO)/losses if losses else 0

    print("\nBacktest Results")
    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("Win Rate:",round(winrate,2),"%")
    print("Profit Factor:",round(pf,2))
    print("Final Capital:",round(capital,2))


# ================= LIVE =================

def live():

    print("\nInstitutional Scanner Started")

    last=None

    while True:

        now=datetime.now(IST)

        if now.weekday()>=5:

            time.sleep(60)
            continue

        if not(9<=now.hour<=15):

            time.sleep(60)
            continue

        if last is None or time.time()-last>SCAN_INTERVAL:

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

                    df=indicators(df)

                    row=df.iloc[-1]

                    direction=entry(row,trend)

                    if direction:

                        momentum=row["rsi"]+row["adx"]

                        candidates.append((stock,direction,row,momentum))

                except:

                    continue

            candidates.sort(key=lambda x:x[3],reverse=True)

            candidates=candidates[:5]

            for s in candidates:

                stock,dir,row,_=s

                msg=f"{dir} {stock} Entry {round(row['Close'],2)}"

                print("Signal:",msg)

                send(msg)

            last=time.time()

        time.sleep(5)


# ================= START =================

if __name__=="__main__":

    backtest()

    live()
