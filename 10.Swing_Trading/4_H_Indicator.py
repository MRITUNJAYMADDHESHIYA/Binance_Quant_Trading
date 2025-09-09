

import time
import hmac, hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone


######################## Global Config ########################
SYMBOL = "SOLUSDT"
INTERVAL = "1m"          # 4-hour candles
KLINE_LIMIT = 500
RISK_PER_TRADE = 0.01    # 1% of equity
ACCOUNT_EQUITY = 10000   # USDT (simulate)
ATR_K = 1.5              # stop distance multiplier
RISK_REWARD = 2.0        # TP at 2x risk
MAX_LEVERAGE = 6         # risk control
POLL_SECONDS = 60 * 10   # poll every 10 minutes for new 4H candle check



############################## Data #######################################
def fetch_klines(symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    cols = ["open_time","open","high","low","close","volume","close_time","qav","num_trades","taker_base_vol","taker_quote_vol","ignore"]
    df = pd.DataFrame(data, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)
    return df.set_index("open_time")



######################## Technical Indicators ##############################
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/period, adjust=False).mean()
    ma_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]; low = df["low"]; close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()



##################### Position Sizing #####################
def position_size(account_equity: float, risk_pct: float, entry_price: float, stop_price: float, max_leverage: float = 6.0):
    risk_usdt = abs(entry_price - stop_price)
    if risk_usdt <= 0:
        return 0.0
    risk_amount = account_equity * risk_pct
    size_in_units = risk_amount / risk_usdt
    return size_in_units

################################# Trading Bot #################################
@dataclass
class Trade:
    side: str  # 'LONG' or 'SHORT'
    entry_time: datetime
    entry_price: float
    size: float
    stop: float
    tp: float
    closed: bool = False
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None

class SwingBot:
    def __init__(self, symbol: str, interval: str):
        self.symbol = symbol
        self.interval = interval
        self.trades: List[Trade] = []
        self.last_signal = None

####################### Signal Generation ##########################
    def compute_signals(self, df: pd.DataFrame) -> pd.Series:
        df = df.copy()
        df["ema8"] = ema(df["close"], 8)
        df["ema34"] = ema(df["close"], 16)
        df["rsi14"] = rsi(df["close"], 7)
        df["atr14"] = atr(df, 8)
        # Cross detection on close
        df["ema_cross"] = 0
        df.loc[(df["ema8"] > df["ema34"]) & (df["ema8"].shift(1) <= df["ema34"].shift(1)), "ema_cross"] = 1   # bullish cross
        df.loc[(df["ema8"] < df["ema34"]) & (df["ema8"].shift(1) >= df["ema34"].shift(1)), "ema_cross"] = -1  # bearish cross
        return df

######################## Place Orders ##########################
    def run_once(self, account_equity=ACCOUNT_EQUITY):
        df = fetch_klines(self.symbol, self.interval, KLINE_LIMIT)
        df = self.compute_signals(df)
        last_row = df.iloc[-1]
        now = df.index[-1].to_pydatetime()

        # Check for cross
        cross = last_row["ema_cross"]
        rsi = last_row["rsi14"]
        atr_v = last_row["atr14"]
        price = last_row["close"]

        # Long entry condition
        if cross == 1 and 40 <= rsi <= 70:
            entry_price = price
            stop = entry_price - ATR_K * atr_v
            tp = entry_price + RISK_REWARD * (entry_price - stop)
            size = position_size(account_equity, RISK_PER_TRADE, entry_price, stop, MAX_LEVERAGE)
            # basic guard
            if size > 0.001:
                trade = Trade("LONG", now, entry_price, size, stop, tp)
                self.trades.append(trade)
                print(f"[{now}] SIGNAL LONG entry={entry_price:.3f} size={size:.5f} stop={stop:.3f} tp={tp:.3f} rsi={rsi:.2f}")
            else:
                print(f"[{now}] LONG signal but size too small: {size:.6f}")

        # Short entry condition
        if cross == -1 and 30 <= rsi <= 60:
            entry_price = price
            stop = entry_price + ATR_K * atr_v
            tp = entry_price - RISK_REWARD * (stop - entry_price)
            size = position_size(account_equity, RISK_PER_TRADE, entry_price, stop, MAX_LEVERAGE)
            if size > 0.001:
                trade = Trade("SHORT", now, entry_price, size, stop, tp)
                self.trades.append(trade)
                print(f"[{now}] SIGNAL SHORT entry={entry_price:.3f} size={size:.5f} stop={stop:.3f} tp={tp:.3f} rsi={rsi:.2f}")
            else:
                print(f"[{now}] SHORT signal but size too small: {size:.6f}")

        # Exit logic for open trades (simple: if price hits stop or tp)
        for trade in self.trades:
            if trade.closed:
                continue
            # for simulation, check last candle high/low to see if stop/tp would have hit
            high = last_row["high"]; low = last_row["low"]
            if trade.side == "LONG":
                # hit TP?
                if low <= trade.stop:
                    trade.closed = True
                    trade.exit_time = now
                    trade.exit_price = trade.stop
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.size
                    print(f"[{now}] LONG STOP hit at {trade.exit_price:.3f} PnL={trade.pnl:.2f}")
                elif high >= trade.tp:
                    trade.closed = True
                    trade.exit_time = now
                    trade.exit_price = trade.tp
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.size
                    print(f"[{now}] LONG TP hit at {trade.exit_price:.3f} PnL={trade.pnl:.2f}")
            else:  # SHORT
                if high >= trade.stop:
                    trade.closed = True
                    trade.exit_time = now
                    trade.exit_price = trade.stop
                    trade.pnl = (trade.entry_price - trade.exit_price) * trade.size
                    print(f"[{now}] SHORT STOP hit at {trade.exit_price:.3f} PnL={trade.pnl:.2f}")
                elif low <= trade.tp:
                    trade.closed = True
                    trade.exit_time = now
                    trade.exit_price = trade.tp
                    trade.pnl = (trade.entry_price - trade.exit_price) * trade.size
                    print(f"[{now}] SHORT TP hit at {trade.exit_price:.3f} PnL={trade.pnl:.2f}")

    def summary(self):
        closed = [t for t in self.trades if t.closed]
        total_pnl = sum(t.pnl for t in closed if t.pnl is not None)
        wins = sum(1 for t in closed if t.pnl and t.pnl > 0)
        losses = sum(1 for t in closed if t.pnl and t.pnl <= 0)
        print(f"Trades: {len(self.trades)} closed: {len(closed)} wins: {wins} losses: {losses} total_pnl: {total_pnl:.2f}")


########################## Run ##########################
if __name__ == "__main__":
    bot = SwingBot(SYMBOL, INTERVAL)
    # Single-run for backtest / immediate check:
    bot.run_once(account_equity=ACCOUNT_EQUITY)
    bot.summary()

    # If you want a polling loop (for paper trading), uncomment below:
    while True:
        try:
            bot.run_once(account_equity=ACCOUNT_EQUITY)
        except Exception as e:
            print("Error:", e)
        time.sleep(POLL_SECONDS)
