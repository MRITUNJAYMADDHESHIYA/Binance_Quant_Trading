#!/usr/bin/env python3
"""
Backtester for the user's percent-change scalp strategy on Binance USDT-M futures style data.

Strategy summary (mirrors your live bot defaults):
- On each new candle t, compute prev candle (t-1) % change = (close-open)/open*100.
- If change > per_change_threshold => open LONG at open[t].
- If change < -per_change_threshold => open SHORT at open[t].
- Single position at a time (max_position=1).
- Risk sizing: risk_fraction * balance per trade.
- Stop loss offset: max(0.5% of previous candle range, 0.0001).
- Take profit: ±1.5% from entry price (multiplicative).
- Fees: taker fee applied on both entry and exit (default 0.05% each side).
- Leverage considered only for margin check (not for PnL calc which is mark-to-market on notional).
- Intrabar execution model: determines which of TP/SL triggers first when both are touched within a candle.

Input data format (CSV):
- Columns: timestamp, open, high, low, close, volume
- timestamp may be ms since epoch or an ISO datetime string. Backtester keeps everything in naive UTC for simplicity.

Outputs:
- Printed summary stats and a CSV with equity curve & trades in /mnt/data (if running in a notebook)
- Functions return dicts so you can import and reuse.

Usage examples (CLI):
  python scalp_backtest.py --csv path/to/SOLUSDT-1m.csv --symbol SOLUSDT \
      --threshold 1.0 --risk-fraction 0.5 --leverage 20 --taker-fee 0.0005

  python scalp_backtest.py --csv path.csv --touch-order pessimistic

"""
import argparse
import math
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------- Config dataclasses ----------------------------
@dataclass
class StrategyConfig:
    per_change_threshold: float = 1.0  # percent (e.g., 1.0 means 1%)
    risk_fraction: float = 0.5         # percent of account risked PER TRADE (e.g., 0.5 => 0.5%)
    tp_multiplier: float = 0.015       # +1.5% TP for long (and -1.5% for short)
    sl_prev_range_pct: float = 0.005   # 0.5% of previous candle range

    sl_min_tick: float = 0.0001
    max_position: int = 1

@dataclass
class MarketConfig:
    leverage: int = 20
    taker_fee: float = 0.0005  # 0.05% per side
    min_notional: float = 5.0  # Binance futures rule

@dataclass
class BacktestConfig:
    initial_balance: float = 1000.0
    touch_order: str = "pessimistic"  # "pessimistic", "optimistic", "tp-first", "sl-first"
    slippage_bps: float = 0.0          # optional slippage in basis points per fill

# ---------------------------- Utility functions ----------------------------

def _parse_timestamp(ts):
    """Parse timestamp from ms epoch or ISO string into pandas Timestamp (UTC naive)."""
    try:
        # ms epoch (int or float)
        ts_val = float(ts)
        if ts_val > 10_000_000_000:  # probably ms
            return pd.to_datetime(int(ts_val), unit="ms", utc=True).tz_convert(None)
        else:  # seconds
            return pd.to_datetime(int(ts_val), unit="s", utc=True).tz_convert(None)
    except Exception:
        # ISO string
        return pd.to_datetime(ts, utc=True).tz_convert(None)


def load_ohlcv_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    for r in required:
        if r not in [c.lower() for c in df.columns]:
            raise ValueError(f"CSV missing required column: {r}")
    # Normalize columns
    df = df.rename(columns={cols.get("timestamp"): "timestamp",
                            cols.get("open"): "open",
                            cols.get("high"): "high",
                            cols.get("low"): "low",
                            cols.get("close"): "close",
                            cols.get("volume"): "volume"})
    df["timestamp"] = df["timestamp"].apply(_parse_timestamp)
    df = df.sort_values("timestamp").reset_index(drop=True)
    # ensure numeric
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df

# ---------------------------- Core backtest logic ----------------------------

@dataclass
class Position:
    side: str          # "long" or "short"
    entry: float
    qty: float
    tp: float
    sl: float
    entry_time: pd.Timestamp


def _intrabar_exit_price(candle: pd.Series, pos: Position, touch_order: str) -> Optional[Tuple[float, str]]:
    """
    Given a candle (open, high, low, close) and a position, determine exit price and reason.
    Returns (exit_price, reason) or None if no exit this candle.
    """
    o, h, l = float(candle.open), float(candle.high), float(candle.low)

    # If both TP and SL are hit within the candle, the order-of-touch rules apply.
    if pos.side == "long":
        tp_hit = h >= pos.tp
        sl_hit = l <= pos.sl
        if not tp_hit and not sl_hit:
            return None
        if tp_hit and sl_hit:
            if touch_order == "pessimistic":
                return pos.sl, "SL"
            elif touch_order == "optimistic":
                return pos.tp, "TP"
            elif touch_order == "tp-first":
                return pos.tp, "TP"
            elif touch_order == "sl-first":
                return pos.sl, "SL"
        return (pos.tp, "TP") if tp_hit else (pos.sl, "SL")
    else:  # short
        tp_hit = l <= pos.tp
        sl_hit = h >= pos.sl
        if not tp_hit and not sl_hit:
            return None
        if tp_hit and sl_hit:
            if touch_order == "pessimistic":
                return pos.sl, "SL"
            elif touch_order == "optimistic":
                return pos.tp, "TP"
            elif touch_order == "tp-first":
                return pos.tp, "TP"
            elif touch_order == "sl-first":
                return pos.sl, "SL"
        return (pos.tp, "TP") if tp_hit else (pos.sl, "SL")


def _apply_slippage(price: float, side: str, slippage_bps: float) -> float:
    # bps to fraction
    slip = slippage_bps / 10_000.0
    if slip <= 0:
        return price
    if side == "buy":
        return price * (1 + slip)
    else:
        return price * (1 - slip)


def _order_fee(notional: float, taker_fee: float) -> float:
    return notional * taker_fee


def _calc_qty(risk_amount: float, entry: float, sl: float, side: str) -> float:
    if side == "long":
        risk_per_unit = max(entry - sl, 1e-12)
    else:
        risk_per_unit = max(sl - entry, 1e-12)
    return max(risk_amount / risk_per_unit, 0.0)


def _pnl(entry: float, exit: float, qty: float, side: str) -> float:
    if side == "long":
        return (exit - entry) * qty
    else:
        return (entry - exit) * qty


def backtest(df: pd.DataFrame,
             strat: StrategyConfig,
             market: MarketConfig,
             bt: BacktestConfig,
             symbol: str = "SYMBOL") -> Dict:
    """Run backtest on a 1m OHLCV DataFrame sorted by timestamp."""
    balance = bt.initial_balance
    equity_curve = []  # list of dicts
    trades: List[Dict] = []
    pos: Optional[Position] = None

    # iterate from second row (need previous candle to form signal)
    for i in range(1, len(df)):
        prev = df.iloc[i-1]
        cur = df.iloc[i]

        # record equity each bar
        equity_curve.append({
            "timestamp": cur.timestamp,
            "balance": balance,
            "position": pos.side if pos else "flat"
        })

        # Manage open position first (exit intrabar if TP/SL touched)
        if pos is not None:
            exit_decision = _intrabar_exit_price(cur, pos, bt.touch_order)
            if exit_decision is not None:
                exit_price, reason = exit_decision
                # fees on exit
                exit_notional = abs(exit_price * pos.qty)
                fee_exit = _order_fee(exit_notional, market.taker_fee)
                pnl = _pnl(pos.entry, exit_price, pos.qty, pos.side)
                balance += pnl - fee_exit

                trades.append({
                    "entry_time": pos.entry_time,
                    "exit_time": cur.timestamp,
                    "side": pos.side,
                    "entry": pos.entry,
                    "exit": exit_price,
                    "qty": pos.qty,
                    "pnl": pnl - fee_exit,
                    "reason": reason
                })
                pos = None
                # after exiting, we continue to signal evaluation on this bar (flat)

        # Generate signal for new entries only at the OPEN of current bar using prev candle
        if pos is None:
            change_pct = (float(prev.close) - float(prev.open)) * 100.0 / max(float(prev.open), 1e-12)
            signal = "neutral"
            if change_pct > strat.per_change_threshold:
                signal = "bullish"
            elif change_pct < -strat.per_change_threshold:
                signal = "bearish"

            if signal != "neutral":
                entry_price = float(cur.open)
                # # compute SL/TP from prev candle range
                # prev_range = float(prev.high) - float(prev.low)
                # sl_offset = max(strat.sl_prev_range_pct * prev_range, strat.sl_min_tick)

                # if signal == "bullish":
                #     sl = entry_price - sl_offset
                #     tp = entry_price * (1 + strat.tp_multiplier)
                #     side = "long"
                #     raw_side = "buy"
                # else:
                #     sl = entry_price + sl_offset
                #     tp = entry_price * (1 - strat.tp_multiplier)
                #     side = "short"
                #     raw_side = "sell"

##########################################################################################
                if signal == "bullish":
                    sl = entry_price * (1 - strat.sl_prev_range_pct)   # 0.5% below entry
                    tp = entry_price * (1 + strat.tp_multiplier)       # 1.5% above entry
                    side = "long"
                    raw_side = "buy"
                else:
                    sl = entry_price * (1 + strat.sl_prev_range_pct)   # 0.5% above entry
                    tp = entry_price * (1 - strat.tp_multiplier)       # 1.5% below entry
                    side = "short"
                    raw_side = "sell"


                # Risk sizing
                risk_amount = balance * (strat.risk_fraction / 100.0)
                qty = _calc_qty(risk_amount, entry_price, sl, side)

                # Enforce min notional and leverage constraint
                notional = abs(entry_price * qty)
                # slippage + fee on entry
                entry_px_slipped = _apply_slippage(entry_price, raw_side, bt.slippage_bps)
                entry_fee = _order_fee(notional, market.taker_fee)

                # Margin required
                margin_required = notional / max(market.leverage, 1)
                if qty <= 0 or notional < market.min_notional or margin_required > balance:
                    # skip entry
                    continue

                # Enter position: deduct fee only (margin is not deducted from balance in futures; we simulate available balance decrease only by fees)
                balance -= entry_fee
                pos = Position(side=side, entry=entry_px_slipped, qty=qty, tp=tp, sl=sl, entry_time=cur.timestamp)

    # If position still open at end, close at last close
    if pos is not None:
        final_close = float(df.iloc[-1].close)
        exit_notional = abs(final_close * pos.qty)
        fee_exit = _order_fee(exit_notional, market.taker_fee)
        pnl = _pnl(pos.entry, final_close, pos.qty, pos.side)
        balance += pnl - fee_exit
        trades.append({
            "entry_time": pos.entry_time,
            "exit_time": df.iloc[-1].timestamp,
            "side": pos.side,
            "entry": pos.entry,
            "exit": final_close,
            "qty": pos.qty,
            "pnl": pnl - fee_exit,
            "reason": "EOD"
        })
        pos = None

    # Build results
    eq = pd.DataFrame(equity_curve)
    tr = pd.DataFrame(trades)

    # Performance stats
    total_trades = int(len(tr))
    wins = int((tr["pnl"] > 0).sum()) if total_trades > 0 else 0
    losses = total_trades - wins
    win_rate = (wins / total_trades) * 100.0 if total_trades > 0 else 0.0
    pnl_total = tr["pnl"].sum() if total_trades > 0 else 0.0

    # Max drawdown on equity
    if not eq.empty:
        eq_series = eq["balance"].astype(float)
        roll_max = eq_series.cummax()
        drawdown = (eq_series - roll_max)
        max_dd = float(drawdown.min())
        max_dd_pct = float(((eq_series / roll_max) - 1.0).min() * 100.0)
    else:
        max_dd = 0.0
        max_dd_pct = 0.0

    # Simple Sharpe using per-bar equity returns (assumes 1m bars; not annualized properly)
    if not eq.empty:
        rets = eq["balance"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        sharpe = float(np.sqrt(60*24*365) * (rets.mean() / (rets.std() + 1e-12))) if len(rets) > 1 else 0.0
    else:
        sharpe = 0.0

    summary = {
        "symbol": symbol,
        "initial_balance": bt.initial_balance,
        "final_balance": float(eq["balance"].iloc[-1]) if not eq.empty else bt.initial_balance,
        "total_pnl": float(pnl_total),
        "total_trades": total_trades,
        "win_rate_pct": float(win_rate),
        "max_drawdown": float(max_dd),
        "max_drawdown_pct": float(max_dd_pct),
        "sharpe_like": sharpe,
        "config": {
            "strategy": asdict(strat),
            "market": asdict(market),
            "backtest": asdict(bt),
        }
    }

    return {
        "summary": summary,
        "equity_curve": eq,
        "trades": tr,
    }



import mplfinance as mpf
import numpy as np

def plot_trades(df: pd.DataFrame, trades: pd.DataFrame, symbol: str):
    """
    Plot candlesticks with trade markers.
    - Green UP arrow for LONG entries
    - Red DOWN arrow for SHORT entries
    - Black 'x' for exits
    """
    # Prepare OHLC for mplfinance
    df_plot = df.set_index("timestamp")[["open","high","low","close","volume"]]

    # Initialize marker Series
    long_marker = pd.Series(np.nan, index=df_plot.index)
    short_marker = pd.Series(np.nan, index=df_plot.index)
    exit_marker = pd.Series(np.nan, index=df_plot.index)

    # Place markers at trade points
    for _, tr in trades.iterrows():
        if tr["entry_time"] in long_marker.index:
            if tr["side"] == "long":
                long_marker.loc[tr["entry_time"]] = tr["entry"]
            else:
                short_marker.loc[tr["entry_time"]] = tr["entry"]
        if tr["exit_time"] in exit_marker.index:
            exit_marker.loc[tr["exit_time"]] = tr["exit"]

    # Create addplot objects
    apds = []
    apds.append(mpf.make_addplot(long_marker, type="scatter", markersize=100, marker="^", color="g"))
    apds.append(mpf.make_addplot(short_marker, type="scatter", markersize=100, marker="v", color="r"))
    apds.append(mpf.make_addplot(exit_marker, type="scatter", markersize=80, marker="x", color="k"))

    # Plot candles with trades
    mpf.plot(df_plot,
             type="candle",
             style="yahoo",
             addplot=apds,
             title=f"{symbol} - Trades",
             ylabel="Price",
             ylabel_lower="Volume",
             volume=True,
             figratio=(16,8),
             figscale=1.2)



# ---------------------------- CLI wiring ----------------------------

def main():
    p = argparse.ArgumentParser(description="Backtest percent-change scalp strategy")
    p.add_argument("--csv", required=True, help="Path to CSV with OHLCV (timestamp,open,high,low,close,volume)")
    p.add_argument("--symbol", default="SOLUSDT")
    p.add_argument("--threshold", type=float, default=1.0, help="Percent change threshold (1.0 => 1%)")
    p.add_argument("--risk-fraction", type=float, default=0.5, help="Risk per trade in PERCENT of balance (0.5 => 0.5%)")
    p.add_argument("--leverage", type=int, default=20)
    p.add_argument("--taker-fee", type=float, default=0.0005)
    p.add_argument("--min-notional", type=float, default=5.0)
    p.add_argument("--touch-order", choices=["pessimistic", "optimistic", "tp-first", "sl-first"], default="pessimistic")
    p.add_argument("--slippage-bps", type=float, default=0.0)
    p.add_argument("--initial-balance", type=float, default=1000.0)

    args = p.parse_args()

    df = load_ohlcv_csv(args.csv)

    strat = StrategyConfig(per_change_threshold=args.threshold, risk_fraction=args.risk_fraction)
    market = MarketConfig(leverage=args.leverage, taker_fee=args.taker_fee, min_notional=args.min_notional)
    bt = BacktestConfig(initial_balance=args.initial_balance, touch_order=args.touch_order, slippage_bps=args.slippage_bps)
    
    res = backtest(df, strat, market, bt, symbol=args.symbol)

    # Save outputs next to input path
    out_prefix = args.csv.rsplit(".csv", 1)[0]
    eq_path = out_prefix + "_equity.csv"
    tr_path = out_prefix + "_trades.csv"
    pd.DataFrame(res["equity_curve"]).to_csv(eq_path, index=False)
    pd.DataFrame(res["trades"]).to_csv(tr_path, index=False)

    print("\nSummary:")
    for k, v in res["summary"].items():
        if k != "config":
            print(f"  {k}: {v}")
    print(f"\nSaved equity to: {eq_path}")
    print(f"Saved trades to: {tr_path}")


    # Plot candlesticks with trades
    if not res["trades"].empty:
        plot_trades(df, res["trades"], args.symbol)


    #Plot equity curve
    eq = res["equity_curve"]
    if not eq.empty:
        plt.figure(figsize=(12,6))
        plt.plot(eq["timestamp"], eq["balance"], label="Equity Curve", color="blue")
        plt.title(f"Equity Curve - {args.symbol}")
        plt.xlabel("Time")
        plt.ylabel("Balance (USDT)")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()





# present in current folder
# python Back_Test.py --csv "SOLUSDT-1m.csv" --symbol SOLUSDT --threshold 1.0 --risk-fraction 0.5 --leverage 20 --taker-fee 0.0005

