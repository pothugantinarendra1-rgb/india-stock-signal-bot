import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# =========================
# CONFIG
# =========================
MODE = "BACKTEST"  # "LIVE" or "BACKTEST"

START_CAPITAL = 100000
RISK_PER_TRADE = 0.02
RR_RATIO = 2.5

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS"
]

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    if BOT_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        except:
            pass

# =========================
# SAFE DOWNLOAD
# =========================
def download_data(symbol):
    df = yf.download(symbol, period="60d", interval="15m", progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# =========================
# ADD INDICATORS
# =========================
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
    df["hh20"] = df["High"].rolling(20).max()
    df["ll20"] = df["Low"].rolling(20).min()

    df.dropna(inplace=True)
    return df

# =========================
# LIVE STRATEGY
# =========================
def run_live():

    print("Professional Live Strategy Running")

    while True:

        now = datetime.now(IST)

        if now.weekday() >= 5:
            time.sleep(60)
            continue

        if now.minute % 15 == 0 and now.second < 5:

            for stock in stocks:

                try:
                    df = download_data(stock)
                    if df is None or len(df) < 100:
                        continue

                    df = add_indicators(df)

                    latest = df.iloc[-1]

                    # BUY
                    if (
                        latest["ema20"] > latest["ema50"]
                        and latest["adx"] > 25
                        and latest["Close"] > latest["hh20"]
                        and latest["rsi"] > 60
                        and latest["Volume"] > 1.5 * latest["vol_avg"]
                    ):

                        sl = latest["Close"] - 1.2 * latest["atr"]
                        target = latest["Close"] + RR_RATIO * (latest["Close"] - sl)

                        send_telegram(f"""
BUY SIGNAL
Stock: {stock}
Entry: {round(latest['Close'],2)}
SL: {round(sl,2)}
Target: {round(target,2)}
RR: 1:{RR_RATIO}
""")

                except Exception as e:
                    print("Live Error:", stock, e)

            time.sleep(60)

        time.sleep(2)

# =========================
# BACKTEST
# =========================
def backtest():

    capital = START_CAPITAL
    total = wins = losses = 0
    gross_profit = gross_loss = 0

    for stock in stocks:

        df = download_data(stock)
        if df is None or len(df) < 200:
            continue

        df = add_indicators(df)
        df = df.tail(45 * 25)

        for i in range(50, len(df)-10):

            row = df.iloc[i]

            if (
                row["ema20"] > row["ema50"]
                and row["adx"] > 25
                and row["Close"] > row["hh20"]
                and row["rsi"] > 60
                and row["Volume"] > 1.5 * row["vol_avg"]
            ):

                price = row["Close"]
                sl = price - 1.2 * row["atr"]
                target = price + RR_RATIO * (price - sl)

                risk_amt = capital * RISK_PER_TRADE
                qty = risk_amt / abs(price - sl)

                future = df.iloc[i+1:i+11]
                result = None

                for _, f in future.iterrows():
                    if f["Low"] <= sl:
                        result = "SL"
                        break
                    if f["High"] >= target:
                        result = "TARGET"
                        break

                total += 1

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
        print("No trades found")
        return

    print("\n===== PROFESSIONAL BACKTEST RESULTS =====")
    print("Total Trades:", total)
    print("Wins:", wins)
    print("Losses:", losses)
    print("Win Rate:", round((wins/total)*100,2), "%")
    print("Profit Factor:", round(gross_profit/gross_loss,2))
    print("Final Capital:", round(capital,2))
    print("=========================================")

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":

    if MODE == "LIVE":
        run_live()
    else:
        backtest()
