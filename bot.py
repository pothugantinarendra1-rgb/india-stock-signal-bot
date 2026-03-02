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

START_CAPITAL = 100000        # ₹1,00,000
RISK_PER_TRADE = 0.02         # 2% risk per trade

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
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except:
        pass

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
            # 15m data allowed up to 60 days
            df = yf.download(stock, period="60d", interval="15m", progress=False)

            if df.empty or len(df) < 200:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                close = df["Close"].iloc[:, 0]
                high = df["High"].iloc[:, 0]
                low = df["Low"].iloc[:, 0]
            else:
                close = df["Close"]
                high = df["High"]
                low = df["Low"]

            df["ema20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
            df["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()
            df["rsi"] = ta.momentum.RSIIndicator(close, 14).rsi()
            df["atr"] = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()

            df.dropna(inplace=True)

            # Approximate last 45 trading days
            df = df.tail(45 * 25)  # ~25 candles per day (15m)

            for i in range(50, len(df)-10):

                ema20_now = df["ema20"].iloc[i]
                ema50_now = df["ema50"].iloc[i]
                ema20_prev = df["ema20"].iloc[i-1]
                ema50_prev = df["ema50"].iloc[i-1]
                rsi_now = df["rsi"].iloc[i]
                atr_now = df["atr"].iloc[i]
                price = df["Close"].iloc[i]

                direction = None

                if ema20_now > ema50_now and ema20_prev <= ema50_prev and rsi_now > 55:
                    direction = "BUY"
                    sl = price - 1.2 * atr_now
                    target = price + 2 * (price - sl)

                elif ema20_now < ema50_now and ema20_prev >= ema50_prev and rsi_now < 45:
                    direction = "SELL"
                    sl = price + 1.2 * atr_now
                    target = price - 2 * (sl - price)

                if direction:

                    total_trades += 1
                    risk_amount = capital * RISK_PER_TRADE
                    position_size = risk_amount / abs(price - sl)

                    future = df.iloc[i+1:i+11]
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

    print("========== BACKTEST RESULTS ==========")
    print("Total Trades:", total_trades)
    print("Wins:", wins)
    print("Losses:", losses)
    print("Success Rate: {:.2f}%".format(success_rate))
    print("Failure Rate: {:.2f}%".format(failure_rate))
    print("Highest RR Achieved: {:.2f}".format(highest_rr))
    print("Profit Factor:", round(profit_factor,2))
    print("Expectancy per Trade:", round(expectancy,2))
    print("Final Capital:", round(capital,2))
    print("======================================")

# ====================================
# LIVE MODE (UNCHANGED)
# ====================================
def live_mode():

    print("Live Mode Started")

    while True:

        now = datetime.now(IST)

        if now.weekday() >= 5:
            time.sleep(60)
            continue

        if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and now.hour < 15:

            if now.minute % 15 == 0 and now.second < 5:
                print("Scanning at", now)
                send_telegram("Scanning market...")
                time.sleep(60)

        time.sleep(2)

# ====================================
# ENTRY POINT
# ====================================
if __name__ == "__main__":

    if MODE == "BACKTEST":
        backtest_strategy()
    else:
        live_mode()
