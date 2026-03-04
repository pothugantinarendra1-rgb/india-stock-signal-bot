import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# ================= CONFIG =================

SCAN_INTERVAL = 900  # 15 minutes
RR_RATIO = 2
RISK_PER_TRADE = 0.015
START_CAPITAL = 100000

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

# ================= STOCK LIST =================

stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS","ONGC.NS",
"TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","COALINDIA.NS",
"DRREDDY.NS","SUNPHARMA.NS","CIPLA.NS","DIVISLAB.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","HDFCLIFE.NS","SBILIFE.NS",
"TATAMOTORS.NS","POLYCAB.NS","MPHASIS.NS","MUTHOOTFIN.NS",
"LUPIN.NS","AUROPHARMA.NS","ALKEM.NS","ASHOKLEY.NS",
"SRF.NS","TRENT.NS","ZEEL.NS","CANBK.NS","BANKBARODA.NS",
"PNB.NS","FEDERALBNK.NS"
]

# ================= TELEGRAM =================

def send_telegram(msg):

    if BOT_TOKEN and CHAT_ID:

        try:
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})
        except:
            pass


# ================= DATA =================

def download_batch():

    df=yf.download(
        tickers=" ".join(stocks),
        period="60d",
        interval="15m",
        group_by="ticker",
        progress=False,
        threads=True
    )

    return df


# ================= INDICATORS =================

def add_indicators(df):

    df["ema20"]=ta.trend.EMAIndicator(df["Close"],20).ema_indicator()
    df["ema50"]=ta.trend.EMAIndicator(df["Close"],50).ema_indicator()

    df["rsi"]=ta.momentum.RSIIndicator(df["Close"],14).rsi()

    df["adx"]=ta.trend.ADXIndicator(
        df["High"],df["Low"],df["Close"],14
    ).adx()

    df["atr"]=ta.volatility.AverageTrueRange(
        df["High"],df["Low"],df["Close"],14
    ).average_true_range()

    df["atr_avg"]=df["atr"].rolling(20).mean()

    df["vol_avg"]=df["Volume"].rolling(20).mean()

    df["hh10"]=df["High"].rolling(10).max().shift(1)
    df["ll10"]=df["Low"].rolling(10).min().shift(1)

    df["vwap"]=(df["Close"]*df["Volume"]).cumsum()/df["Volume"].cumsum()

    df.dropna(inplace=True)

    return df


# ================= MARKET TREND =================

def get_market_trend():

    df=yf.download("^NSEI",period="60d",interval="60m",progress=False)

    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    close=df["Close"].astype(float)

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if ema20.iloc[-1]>ema50.iloc[-1]:
        return "BULL"

    return "BEAR"


# ================= ENTRY LOGIC =================

def check_entry(row,trend):

    momentum=row["rsi"]+row["adx"]

    if trend=="BULL":

        if row["ema20"]<=row["ema50"]:
            return None

        if row["Close"]<=row["hh10"]:
            return None

        if row["Close"]<=row["vwap"]:
            return None

        if row["Volume"]<=1.5*row["vol_avg"]:
            return None

        if row["atr"]<=row["atr_avg"]:
            return None

        return ("BUY",momentum)

    else:

        if row["ema20"]>=row["ema50"]:
            return None

        if row["Close"]>=row["ll10"]:
            return None

        if row["Close"]>=row["vwap"]:
            return None

        if row["Volume"]<=1.5*row["vol_avg"]:
            return None

        if row["atr"]<=row["atr_avg"]:
            return None

        return ("SELL",momentum)


# ================= BACKTEST =================

def run_backtest():

    print("\nRunning Strategy Backtest...\n")

    data=download_batch()

    capital=START_CAPITAL

    trades=0
    wins=0
    losses=0

    for stock in stocks:

        try:

            df=data[stock]

            if df.empty:
                continue

            df=df.astype(float)

            df=add_indicators(df)

            for i in range(len(df)-10):

                row=df.iloc[i]

                result=check_entry(row,"BULL")

                if result is None:
                    continue

                trades+=1

                entry=row["Close"]
                atr=row["atr"]

                sl=entry-1.2*atr
                target=entry+RR_RATIO*(entry-sl)

                future=df.iloc[i+1:i+10]

                hit=None

                for _,f in future.iterrows():

                    if f["Low"]<=sl:
                        hit="SL"
                        break

                    if f["High"]>=target:
                        hit="TP"
                        break

                if hit=="TP":

                    wins+=1
                    capital+=capital*RISK_PER_TRADE*RR_RATIO

                else:

                    losses+=1
                    capital-=capital*RISK_PER_TRADE

        except:
            pass

    winrate=(wins/trades*100) if trades>0 else 0

    pf=(wins*RR_RATIO)/losses if losses>0 else 0

    print("Backtest Results")
    print("----------------")
    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("Win Rate:",round(winrate,2),"%")
    print("Profit Factor:",round(pf,2))
    print("Final Capital:",round(capital,2))
    print("\n")


# ================= LIVE BOT =================

def run_live():

    print("Starting Live Scanner")

    last_scan=None

    while True:

        try:

            now=datetime.now(IST)

            if now.weekday()>=5:
                time.sleep(60)
                continue

            if not (9<=now.hour<=15):
                time.sleep(60)
                continue

            if last_scan is None or (time.time()-last_scan)>=SCAN_INTERVAL:

                print("\nRunning scan:",now)

                trend=get_market_trend()

                data=download_batch()

                scanned=0
                signals=[]

                for stock in stocks:

                    print("Scanning:",stock)

                    try:

                        df=data[stock]

                        if df.empty:
                            continue

                        df=df.astype(float)

                        df=add_indicators(df)

                        row=df.iloc[-1]

                        result=check_entry(row,trend)

                        scanned+=1

                        if result is None:
                            continue

                        direction,momentum=result

                        signals.append((stock,direction,row,momentum))

                    except Exception as e:

                        print("Error:",stock,e)

                signals.sort(key=lambda x:x[3],reverse=True)

                signals=signals[:3]

                for stock,direction,row,_ in signals:

                    price=row["Close"]

                    if direction=="BUY":

                        sl=price-1.2*row["atr"]
                        target=price+RR_RATIO*(price-sl)

                    else:

                        sl=price+1.2*row["atr"]
                        target=price-RR_RATIO*(sl-price)

                    msg=f"""
{direction} SIGNAL

Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
"""

                    print("Signal:",stock,direction)

                    send_telegram(msg)

                print("Stocks scanned:",scanned)
                print("Signals found:",len(signals))
                print("Next scan in 15 minutes")

                last_scan=time.time()

            time.sleep(5)

        except Exception as e:

            print("Main error:",e)

            time.sleep(10)


# ================= START =================

if __name__=="__main__":

    run_backtest()

    run_live()
