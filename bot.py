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

# Large Caps
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","SUNPHARMA.NS","DRREDDY.NS","JSWSTEEL.NS",
"TATASTEEL.NS","BAJFINANCE.NS","BAJAJFINSV.NS","HDFCLIFE.NS",
"SBILIFE.NS","ADANIPORTS.NS","ADANIENT.NS","HINDALCO.NS",
"POWERGRID.NS","NTPC.NS","ONGC.NS","DIVISLAB.NS",

# Banks
"CANBK.NS","BANKBARODA.NS","PNB.NS","FEDERALBNK.NS",
"IDFCFIRSTB.NS","INDUSINDBK.NS","AUROPHARMA.NS",

# Midcaps
"POLYCAB.NS","MPHASIS.NS","MUTHOOTFIN.NS","LUPIN.NS",
"ALKEM.NS","SRF.NS","TRENT.NS","ZEEL.NS",
"PAGEIND.NS","PIIND.NS","AUBANK.NS","DEEPAKNTR.NS",
"BALKRISIND.NS","ASHOKLEY.NS","BOSCHLTD.NS","BEL.NS",
"HAL.NS","INDIGO.NS","SIEMENS.NS","TORNTPHARM.NS",
"COLPAL.NS","DABUR.NS","GODREJCP.NS","VEDL.NS",
"TATAMOTORS.NS","HAVELLS.NS","VOLTAS.NS","CUMMINSIND.NS",
"NAUKRI.NS","PERSISTENT.NS","LTIM.NS","COFORGE.NS",
"OBEROIRLTY.NS","DLF.NS","LODHA.NS","IRCTC.NS",
"ABCAPITAL.NS","LICHSGFIN.NS","PEL.NS","ICICIGI.NS",
"ICICIPRULI.NS","TATACOMM.NS","TATAELXSI.NS","LALPATHLAB.NS",
"METROPOLIS.NS","ESCORTS.NS","THERMAX.NS","SUPREMEIND.NS",
"ASTRAL.NS","APLAPOLLO.NS","KEI.NS","FINPIPE.NS"
]

# ================= TELEGRAM =================

def send(msg):

    if BOT_TOKEN and CHAT_ID:

        try:

            url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

            requests.post(url,data={"chat_id":CHAT_ID,"text":msg})

        except:

            pass


# ================= DATA =================

def download():

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

def indicators(df):

    df["ema20"]=ta.trend.EMAIndicator(df["Close"],20).ema_indicator()
    df["ema50"]=ta.trend.EMAIndicator(df["Close"],50).ema_indicator()
    df["ema200"]=ta.trend.EMAIndicator(df["Close"],200).ema_indicator()

    df["atr"]=ta.volatility.AverageTrueRange(
        df["High"],df["Low"],df["Close"],14
    ).average_true_range()

    df["atr_avg"]=df["atr"].rolling(20).mean()

    df["vol_avg"]=df["Volume"].rolling(20).mean()

    df["hh20"]=df["High"].rolling(20).max().shift(1)
    df["ll20"]=df["Low"].rolling(20).min().shift(1)

    df.dropna(inplace=True)

    return df


# ================= MARKET TREND =================

def market_trend():

    df=yf.download("^NSEI",period="60d",interval="60m",progress=False)

    close=df["Close"]

    ema20=ta.trend.EMAIndicator(close,20).ema_indicator()
    ema50=ta.trend.EMAIndicator(close,50).ema_indicator()

    if ema20.iloc[-1]>ema50.iloc[-1]:

        return "BULL"

    return "BEAR"


# ================= ENTRY =================

def entry(row,trend):

    if trend=="BULL":

        if not(row["ema20"]>row["ema50"]>row["ema200"]):
            return None

        if row["Close"]<=row["hh20"]:
            return None

        if row["Volume"]<=2*row["vol_avg"]:
            return None

        if row["atr"]<=row["atr_avg"]:
            return None

        return "BUY"

    else:

        if not(row["ema20"]<row["ema50"]<row["ema200"]):
            return None

        if row["Close"]>=row["ll20"]:
            return None

        if row["Volume"]<=2*row["vol_avg"]:
            return None

        if row["atr"]<=row["atr_avg"]:
            return None

        return "SELL"


# ================= BACKTEST =================

def backtest():

    print("\nRunning Backtest\n")

    data=download()

    capital=START_CAPITAL

    trades=0
    wins=0
    losses=0

    trend=market_trend()

    for stock in stocks:

        try:

            df=data[stock]

            if df.empty:
                continue

            df=indicators(df)

            for i in range(len(df)-20):

                row=df.iloc[i]

                direction=entry(row,trend)

                if direction is None:
                    continue

                trades+=1

                price=row["Close"]
                atr=row["atr"]

                if direction=="BUY":

                    sl=price-1.5*atr
                    tp=price+RR_RATIO*(price-sl)

                else:

                    sl=price+1.5*atr
                    tp=price-RR_RATIO*(sl-price)

                future=df.iloc[i+1:i+20]

                result="SL"

                for _,f in future.iterrows():

                    if direction=="BUY":

                        if f["Low"]<=sl:
                            result="SL"
                            break

                        if f["High"]>=tp:
                            result="TP"
                            break

                    else:

                        if f["High"]>=sl:
                            result="SL"
                            break

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

            pass

    winrate=(wins/trades*100) if trades else 0
    pf=(wins*RR_RATIO)/losses if losses else 0

    print("Trades:",trades)
    print("Wins:",wins)
    print("Losses:",losses)
    print("Win Rate:",round(winrate,2),"%")
    print("Profit Factor:",round(pf,2))
    print("Final Capital:",round(capital,2))


# ================= LIVE =================

def live():

    print("\nLive Scanner Started\n")

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

            print("\nRunning Scan:",now)

            trend=market_trend()

            data=download()

            signals=[]

            for stock in stocks:

                print("Scanning:",stock)

                try:

                    df=data[stock]

                    if df.empty:
                        continue

                    df=indicators(df)

                    row=df.iloc[-1]

                    direction=entry(row,trend)

                    if direction:

                        signals.append((stock,direction,row))

                except:

                    pass

            signals=signals[:3]

            for s in signals:

                stock,dir,row=s

                price=row["Close"]

                msg=f"{dir} {stock} Entry {round(price,2)}"

                print("Signal:",msg)

                send(msg)

            print("Signals:",len(signals))

            last=time.time()

        time.sleep(5)


# ================= START =================

if __name__=="__main__":

    backtest()

    live()
