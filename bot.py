import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# ================= CONFIG =================
MODE = "BACKTEST"   # "LIVE" or "BACKTEST"

START_CAPITAL = 100000
RISK_PER_TRADE = 0.02
RR_RATIO = 2.2

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS"
]

# ================= TELEGRAM =================
def send_telegram(msg):
    if BOT_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        except:
            pass

# ================= DATA DOWNLOAD =================
def get_data(symbol):
    df = yf.download(symbol, period="60d", interval="15m", progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open","High","Low","Close","Volume"]]

# ================= INDICATORS =================
def add_indicators(df):

    df["ema20"] = ta.trend.EMAIndicator(df["Close"], 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["Close"], 50).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["Close"], 14).rsi()
    df["atr"] = ta.volatility.AverageTrueRange(
        df["High"], df["Low"], df["Close"], 14
    ).average_true_range()
    df["adx"] = ta.trend.ADXIndicator(
        df["High"], df["Low"], df["Close"], 14
    ).adx()
    df["vol_avg"] = df["Volume"].rolling(20).mean()

    # 🔥 Relaxed breakout (10 candle lookback)
    df["hh10"] = df["High"].rolling(10).max().shift(1)
    df["ll10"] = df["Low"].rolling(10).min().shift(1)

    df.dropna(inplace=True)
    return df

# ================= ENTRY LOGIC =================
def check_entry(row):

    # BUY
    if (
        row["ema20"] > row["ema50"]
        and row["adx"] > 18
        and row["Close"] > row["hh10"]
        and row["rsi"] > 52
        and row["Volume"] > row["vol_avg"]
    ):
        return "BUY"

    # SELL
    if (
        row["ema20"] < row["ema50"]
        and row["adx"] > 18
        and row["Close"] < row["ll10"]
        and row["rsi"] < 48
        and row["Volume"] > row["vol_avg"]
    ):
        return "SELL"

    return None

# ================= LIVE STRATEGY =================
def run_live():

    print("Balanced Professional LIVE Strategy Running")

    while True:

        now = datetime.now(IST)

        # Skip weekends
        if now.weekday() >= 5:
            time.sleep(60)
            continue

        # Market hours 9:15 to 3:30
        if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and now.hour < 15:

            # Run exactly at 15m close
            if now.minute % 15 == 0 and now.second < 5:

                print("Running 15m scan at", now)

                for stock in stocks:

                    try:
                        df = get_data(stock)
                        if df is None or len(df) < 100:
                            continue

                        df = add_indicators(df)
                        latest = df.iloc[-1]

                        direction = check_entry(latest)

                        if direction:

                            price = latest["Close"]

                            if direction == "BUY":
                                sl = price - 1.2 * latest["atr"]
                                target = price + RR_RATIO * (price - sl)
                            else:
                                sl = price + 1.2 * latest["atr"]
                                target = price - RR_RATIO * (sl - price)

                            message = f"""
{direction} SIGNAL

Stock: {stock}
Entry: {round(price,2)}
SL: {round(sl,2)}
Target: {round(target,2)}
RR: 1:{RR_RATIO}
"""
                            send_telegram(message)
                            print("Signal sent:", stock)

                    except Exception as e:
                        print("Live error:", stock, e)

                time.sleep(60)

        time.sleep(2)

# ================= BACKTEST =================
def backtest():

    capital = START_CAPITAL
    total = wins = losses = 0
    gross_profit = gross_loss = 0

    for stock in stocks:

        df = get_data(stock)
        if df is None or len(df) < 200:
            continue

        df = add_indicators(df)
        df = df.tail(45 * 25)

        for i in range(len(df)-10):

            row = df.iloc[i]
            direction = check_entry(row)

            if not direction:
                continue

            price = row["Close"]

            if direction == "BUY":
                sl = price - 1.2 * row["atr"]
                target = price + RR_RATIO * (price - sl)
            else:
                sl = price + 1.2 * row["atr"]
                target = price - RR_RATIO * (sl - price)

            total += 1

            risk_amt = capital * RISK_PER_TRADE
            qty = risk_amt / abs(price - sl)

            future = df.iloc[i+1:i+11]
            result = None

            for _, f in future.iterrows():

                if direction == "BUY":
                    if f["Low"] <= sl:
                        result = "SL"; break
                    if f["High"] >= target:
                        result = "TARGET"; break
                else:
                    if f["High"] >= sl:
                        result = "SL"; break
                    if f["Low"] <= target:
                        result = "TARGET"; break

            if result == "TARGET":
                profit = qty * abs(target - price)
                capital += profit
                gross_profit += profit
                wins += 1
            elif result == "SL":
                loss = qty * abs(price - sl)
                capital -= loss
                gross_loss += loss
                losses += 1

    if total == 0:
        print("No trades found — logic still too strict")
        return

    print("\n====== BALANCED PROFESSIONAL RESULTS ======")
    print("Total Trades:", total)
    print("Wins:", wins)
    print("Losses:", losses)
    print("Win Rate:", round(wins/total*100,2), "%")
    print("Profit Factor:", round(gross_profit/gross_loss,2))
    print("Final Capital:", round(capital,2))
    print("==========================================")

# ================= ENTRY POINT =================
if __name__ == "__main__":

    if MODE == "BACKTEST":
        backtest()
    else:
        run_live()
