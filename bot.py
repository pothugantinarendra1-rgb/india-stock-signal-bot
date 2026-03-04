import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# ================= CONFIG =================
MODE = "BACKTEST"  # BACKTEST or LIVE

START_CAPITAL = 100000
RISK_PER_TRADE = 0.015
RR_RATIO = 2
DAILY_LOSS_LIMIT = 0.03

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

# ================= STOCK UNIVERSE (85) =================
stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS","ONGC.NS",
"TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","COALINDIA.NS",
"DRREDDY.NS","SUNPHARMA.NS","CIPLA.NS","DIVISLAB.NS",
"BAJFINANCE.NS","BAJAJFINSV.NS","HDFCLIFE.NS","SBILIFE.NS",
"BRITANNIA.NS","GRASIM.NS","HEROMOTOCO.NS",
"ADANIPORTS.NS","ADANIENT.NS","DABUR.NS","PIDILITIND.NS",
"COLPAL.NS","MCDOWELL-N.NS","VEDL.NS","SIEMENS.NS",
"INDIGO.NS","HAL.NS","BEL.NS","BOSCHLTD.NS",
"GODREJCP.NS","TORNTPHARM.NS","ICICIGI.NS","ICICIPRULI.NS",
"TATAMOTORS.NS","LODHA.NS","POLYCAB.NS","PAGEIND.NS",
"MPHASIS.NS","MUTHOOTFIN.NS","LUPIN.NS","AUROPHARMA.NS",
"ALKEM.NS","ASHOKLEY.NS","BALKRISIND.NS","SRF.NS",
"DEEPAKNTR.NS","AUBANK.NS","TRENT.NS","ZEEL.NS",
"CANBK.NS","BANKBARODA.NS","PNB.NS","FEDERALBNK.NS"
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
def get_data(symbol,interval="15m"):
    df=yf.download(symbol,period="60d",interval=interval,progress=False)
    if df.empty: return None
    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)
    return df[["Open","High","Low","Close","Volume"]]

# ================= INDICATORS =================
def add_indicators(df):

    df["ema20"]=ta.trend.EMAIndicator(df["Close"],20).ema_indicator()
    df["ema50"]=ta.trend.EMAIndicator(df["Close"],50).ema_indicator()

    df["rsi"]=ta.momentum.RSIIndicator(df["Close"],14).rsi()

    df["atr"]=ta.volatility.AverageTrueRange(
        df["High"],df["Low"],df["Close"],14
    ).average_true_range()

    df["atr_avg"]=df["atr"].rolling(20).mean()

    df["adx"]=ta.trend.ADXIndicator(
        df["High"],df["Low"],df["Close"],14
    ).adx()

    df["vol_avg"]=df["Volume"].rolling(20).mean()

    df["hh10"]=df["High"].rolling(10).max().shift(1)
    df["ll10"]=df["Low"].rolling(10).min().shift(1)

    df.dropna(inplace=True)

    return df

# ================= NIFTY TREND =================
def get_market_trend():

    df=yf.download("^NSEI",period="60d",interval="60m",progress=False)

    df["ema20"]=ta.trend.EMAIndicator(df["Close"],20).ema_indicator()
    df["ema50"]=ta.trend.EMAIndicator(df["Close"],50).ema_indicator()

    latest=df.iloc[-1]

    if latest["ema20"]>latest["ema50"]:
        return "BULL"
    else:
        return "BEAR"

# ================= ENTRY LOGIC =================
def check_entry(row,trend):

    if (
        trend=="BULL"
        and row["ema20"]>row["ema50"]
        and row["Close"]>row["hh10"]
        and row["adx"]>18
        and row["rsi"]>52
        and row["Volume"]>row["vol_avg"]
        and row["atr"]>row["atr_avg"]
    ):
        return "BUY"

    if (
        trend=="BEAR"
        and row["ema20"]<row["ema50"]
        and row["Close"]<row["ll10"]
        and row["adx"]>18
        and row["rsi"]<48
        and row["Volume"]>row["vol_avg"]
        and row["atr"]>row["atr_avg"]
    ):
        return "SELL"

    return None

# ================= BACKTEST =================
def backtest():

    capital=START_CAPITAL
    wins=losses=total=0
    gross_profit=gross_loss=0

    market_trend=get_market_trend()

    for stock in stocks:

        df=get_data(stock)

        if df is None or len(df)<200:
            continue

        df=add_indicators(df)

        df=df.tail(45*25)

        trades_today={}

        for i in range(len(df)-10):

            row=df.iloc[i]
            date=row.name.date()

            if trades_today.get((stock,date),0)>=3:
                continue

            direction=check_entry(row,market_trend)

            if not direction:
                continue

            price=row["Close"]

            if direction=="BUY":
                sl=price-1.2*row["atr"]
                target=price+RR_RATIO*(price-sl)
            else:
                sl=price+1.2*row["atr"]
                target=price-RR_RATIO*(sl-price)

            risk_amt=capital*RISK_PER_TRADE
            qty=risk_amt/abs(price-sl)

            future=df.iloc[i+1:i+11]

            result=None

            for _,f in future.iterrows():

                if direction=="BUY":
                    if f["Low"]<=sl:
                        result="SL"
                        break
                    if f["High"]>=target:
                        result="TARGET"
                        break

                else:
                    if f["High"]>=sl:
                        result="SL"
                        break
                    if f["Low"]<=target:
                        result="TARGET"
                        break

            if result:

                trades_today[(stock,date)]=trades_today.get((stock,date),0)+1

                total+=1

                if result=="TARGET":

                    profit=qty*abs(target-price)

                    capital+=profit
                    gross_profit+=profit
                    wins+=1

                else:

                    loss=qty*abs(price-sl)

                    capital-=loss
                    gross_loss+=loss
                    losses+=1

    print("\n===== BACKTEST RESULTS =====")
    print("Total Trades:",total)
    print("Wins:",wins)
    print("Losses:",losses)

    if total>0:
        print("Win Rate:",round(wins/total*100,2),"%")
        print("Profit Factor:",round(gross_profit/gross_loss,2))

    print("Final Capital:",round(capital,2))
    print("============================")

# ================= LIVE =================
def run_live():

    print("🚀 Institutional Bot Running")

    trades_today={}

    while True:

        now=datetime.now(IST)

        if now.weekday()>=5:
            time.sleep(60)
            continue

        if not (10<=now.hour<15):
            time.sleep(30)
            continue

        if now.minute%15==0 and now.second<5:

            market_trend=get_market_trend()

            for stock in stocks:

                date_key=now.date()

                if trades_today.get((stock,date_key),0)>=3:
                    continue

                try:

                    df=get_data(stock)

                    if df is None or len(df)<100:
                        continue

                    df=add_indicators(df)

                    latest=df.iloc[-1]

                    if latest["Close"]<150:
                        continue

                    direction=check_entry(latest,market_trend)

                    if direction:

                        price=latest["Close"]

                        if direction=="BUY":
                            sl=price-1.2*latest["atr"]
                            target=price+RR_RATIO*(price-sl)
                        else:
                            sl=price+1.2*latest["atr"]
                            target=price-RR_RATIO*(sl-price)

                        msg=f"""
{direction} SIGNAL

Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
Market Trend: {market_trend}
"""

                        send_telegram(msg)

                        trades_today[(stock,date_key)]=trades_today.get((stock,date_key),0)+1

                        print("Signal:",stock)

                except Exception as e:
                    print("Error:",stock,e)

            time.sleep(60)

        time.sleep(2)

# ================= ENTRY =================
if __name__=="__main__":

    if MODE=="BACKTEST":
        backtest()

    else:
        run_live()
