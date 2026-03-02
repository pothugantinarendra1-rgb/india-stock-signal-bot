import yfinance as yf
import pandas as pd
import ta
import requests
import time
import os
import pytz
from datetime import datetime

# ====================================
# CONFIGURATION
# ====================================
MODE = "BACKTEST"   # Change to "LIVE" for live signals

START_CAPITAL = 100000
RISK_PER_TRADE = 0.02

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = pytz.timezone("Asia/Kolkata")

stocks = [
"RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
"AXISBANK.NS","HCLTECH.NS","BAJFINANCE.NS","ASIANPAINT.NS",
"MARUTI.NS","TITAN.NS","ULTRACEMCO.NS","ONGC.NS","NTPC.NS",
"BPCL.NS","ADANIPORTS.NS","DIVISLAB.NS","APOLLOHOSP.NS",
"BEL.NS","CIPLA.NS","DRREDDY.NS","EICHERMOT.NS","M&M.NS",
"TECHM.NS","SUNPHARMA.NS","JSWSTEEL.NS","TATAMOTORS.NS",
"TATASTEEL.NS","COALINDIA.NS","HINDALCO.NS","BANKBARODA.NS"
]

# ====================================
# TELEGRAM FUNCTION
# ====================================
def send_telegram(message):
    try:
        if BOT_TOKEN and CHAT_ID:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except:
        pass

# ====================================
# SAFE DATA DOWNLOAD
# ====================================
def download_data(symbol):
    df = yf.download(symbol, period="60d", interval="15m", progress=False)

    if df.empty:
        return None

    # 🔥 Flatten MultiIndex immediately
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required_cols = ["Open", "High", "Low", "Close", "Volume"]

    if not all(col in df.columns for col in required_cols):
        return None

    return df[required_cols].copy()

# ====================================
# BACKTEST ENGINE (45 DAYS, 15M)
# ====================================
def backtest_strategy():

    print("Running 45 Trading Day Backtest (15m candles)...\n")

    capital = START_CAPITAL
    total_trades = 0
    wins = 0
    losses = 0
    highest_rr = 0
    gross_profit = 0
    gross_loss = 0

    for stock in stocks:

        try:
            df = download_data(stock)
            if df is None or len(df) < 200:
                continue

            # Indicators
            df["ema20"] = ta.trend.EMAIndicator(df["Close"], 20).ema_indicator()
            df["ema50"] = ta.trend.EMAIndicator(df["Close"], 50).ema_indicator()
            df["rsi"] = ta.momentum.RSIIndicator(df["Close"], 14).rsi()
            df["atr"] = ta.volatility.AverageTrueRange(
                df["High"], df["Low"], df["Close"], 14
            ).average_true_range()

            df.dropna(inplace=True)

            # Last ~45 trading days (~25 candles/day)
            df = df.tail(45 * 25)

            for i in range(50, len(df) - 10):

                ema20_now = df["ema20"].iloc[i]
                ema50_now = df["ema50"].iloc[i]
                ema20_prev = df["ema20"].iloc[i - 1]
                ema50_prev = df["ema50"].iloc[i - 1]
                rsi_now = df["rsi"].iloc[i]
                atr_now = df["atr"].iloc[i]
                price = df["Close"].iloc[i]

                direction = None

                # BUY condition
                if (
                    ema20_now > ema50_now
                    and ema20_prev <= ema50_prev
                    and rsi_now > 55
                ):
                    direction = "BUY"
                    sl = price - 1.2 * atr_now
                    target = price + 2 * (price - sl)

                # SELL condition
                elif (
                    ema20_now < ema50_now
                    and ema20_prev >= ema50_prev
                    and rsi_now < 45
                ):
                    direction = "SELL"
                    sl = price + 1.2 * atr_now
                    target = price - 2 * (sl - price)

                if direction:

                    total_trades += 1
                    risk_amount = capital * RISK_PER_TRADE
                    position_size = risk_amount / abs(price - sl)

                    future = df.iloc[i + 1 : i + 11]
                    result = None

                    for _, row in future.iterrows():

                        if direction == "BUY":
                            if row["Low"] <= sl:
                                result = "SL"
                                break
                            if row["High"] >= target:
                                result = "TARGET"
                                break
                        else:
                            if row["High"] >= sl:
                                result = "SL"
                                break
                            if row["Low"] <= target:
                                result = "TARGET"
                                break

                    rr = abs((target - price) / (price - sl))
                    highest_rr = max(highest_rr, rr)

                    if result == "TARGET":
                        profit = position_size * abs(target - price)
                        capital += profit
                        gross_profit += profit
                        wins += 1
                    elif result == "SL":
                        loss = position_size * abs(price - sl)
                        capital -= loss
                        gross_loss += loss
                        losses += 1

        except Exception as e:
            print("Backtest error:", stock, e)

    if total_trades == 0:
        print("No trades found.")
        return

    success_rate = (wins / total_trades) * 100
    failure_rate = (losses / total_trades) * 100
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
    expectancy = (gross_profit - gross_loss) / total_trades

    print("\n========== BACKTEST RESULTS ==========")
    print("Total Trades:", total_trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("Success Rate: {:.2f}%".format(success_rate))
    print("Failure Rate: {:.2f}%".format(failure_rate))
    print("Highest RR Achieved: {:.2f}".format(highest_rr))
    print("Profit Factor:", round(profit_factor, 2))
    print("Expectancy per Trade:", round(expectancy, 2))
    print("Final Capital:", round(capital, 2))
    print("======================================")

# ====================================
# LIVE MODE (Basic placeholder)
# ====================================
def live_mode():
    print("Live Mode Started")
    while True:
        time.sleep(60)

# ====================================
# ENTRY POINT
# ====================================
if __name__ == "__main__":
    if MODE == "BACKTEST":
        backtest_strategy()
    else:
        live_mode()
