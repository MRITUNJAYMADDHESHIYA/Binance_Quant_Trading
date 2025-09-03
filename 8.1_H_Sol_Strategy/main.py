import asyncio
import logging
from datetime import timezone, datetime, timedelta
from typing import Dict, List

import pandas as pd
import ccxt.async_support as ccxt  #async version

############################################################
# SAFETY: set this to True to log orders instead of sending
############################################################
DRY_RUN = True  # flip to False only after paper testing

############################################################
# Config
############################################################
symbol_ccxt = "SOL/USDT"           # CCXT market symbol (USDT-M futures)
timeframe = "1m"                   # candle timeframe
per_change_threshold = 0.01        # percent change of previous candle
max_position = 1                   # allow max concurrent positions
leverage = 20                      # leverage
poll_interval_sec = 3              # wait 3 seconds between each loop iteration when fetching new data and managing positions.
quote_asset = "USDT"               # account currency
risk_fraction = 0.03               # 3% of account per trade

#########################################################################
API_KEY = "$$$$$$$$$"
API_SECRET = "$$$$$$$$$$$$$$"

############################################################
# Logging
############################################################
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scalp")

############################################################
# State
############################################################
open_positions: List[Dict] = []  # tracked manually(entry_price, quantity, side, tp_price, sl_price)
last_candle_ts = None            # timestamp of the last processed candle(doesn’t re-trade the same candle again and again)

############################################################
# Helpers
############################################################

def to_ist(ms: int) -> datetime:
    # Convert ms timestamp to IST
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) + timedelta(hours=5, minutes=30)


def df_from_ohlcv(ohlcv: List[List]) -> pd.DataFrame:
    # CCXT OHLCV: [timestamp, open, high, low, close, volume]
    rows = []
    for ts, o, h, l, c, v in ohlcv:
        rows.append({
            "timestamp": to_ist(ts),
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": float(v),
            "ts": int(ts),
        })
    return pd.DataFrame(rows)


async def fetch_last_two_candles(exchange: ccxt.binance, symbol: str, timeframe: str) -> pd.DataFrame:
    candles = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=2)
    df = df_from_ohlcv(candles)
    return df


def previous_candle_change_pct(df: pd.DataFrame) -> float:
    """Return percent change of the *previous* (closed) candle.
    Expects the DataFrame to have 2 rows: [prev, latest]
    """
    if df.shape[0] < 2:
        return 0.0
    prev = df.iloc[-2]
    change_pct = (prev["close"] - prev["open"]) * 100.0 / prev["open"]
    return float(change_pct)


def get_signal(change_pct: float) -> str:
    if change_pct > per_change_threshold:
        return "bullish"
    elif change_pct < -per_change_threshold:
        return "bearish"
    else:
        return "neutral"


async def ensure_leverage(exchange: ccxt.binance, symbol: str, lev: int):
    try:
        await exchange.set_leverage(lev, symbol)
    except Exception as e:
        # Some exchanges require marketId; CCXT handles it internally for Binance futures
        logger.warning(f"Could not set leverage via API (may already be set): {e}")


async def fetch_account_balance(exchange: ccxt.binance, asset: str) -> float:
    bal = await exchange.fetch_balance()
    # Prefer 'free' balance for sizing
    wallets = bal.get(asset) or {}
    if isinstance(wallets, dict):
        free_amt = wallets.get('free') or wallets.get('total') or 0.0
    else:
        free_amt = 0.0
    return float(free_amt)


async def place_market_order(exchange: ccxt.binance, symbol: str, side: str, amount: float):
    if DRY_RUN:
        logger.info(f"[DRY_RUN] create_order {side} {amount} {symbol}")
        return {"id": "dry-run"}
    order = await exchange.create_order(symbol=symbol, type="market", side=side, amount=amount)
    return order


################################################## Position Managment #####################################
async def manage_positions(exchange: ccxt.binance, current_price: float):
    global open_positions
    keep: List[Dict] = []
    try:
        for pos in open_positions:
            side =  pos["side"]
            tp   =  pos["tp_price"]
            sl   =  pos["sl_price"]
            qty  =  pos["quantity"]
            if side == "long":
                if current_price >= tp:
                    logger.info(f"TP hit for LONG at {tp:.4f}")
                    await place_market_order(exchange, symbol_ccxt, "sell", qty)
                    continue
                if current_price <= sl:
                    logger.info(f"SL hit for LONG at {sl:.4f}")
                    await place_market_order(exchange, symbol_ccxt, "sell", qty)
                    continue
            else:  ############# short
                if current_price <= tp:
                    logger.info(f"TP hit for SHORT at {tp:.4f}")
                    await place_market_order(exchange, symbol_ccxt, "buy", qty)
                    continue
                if current_price >= sl:
                    logger.info(f"SL hit for SHORT at {sl:.4f}")
                    await place_market_order(exchange, symbol_ccxt, "buy", qty)
                    continue
            keep.append(pos)
        open_positions = keep

    except Exception as e:
        logger.error(f"Error managing positions: {e}")
        return


################################################## Order Placed #############################################################
async def execute_trade(exchange: ccxt.binance, signal: str, current_price: float, prev_candle: Dict, account_balance: float):
    global open_positions
    if len(open_positions) >= max_position:
        logger.info("Max position limit reached; skipping new trade.")
        return

    # Risk sizing
    risk_amount = account_balance * risk_fraction
    candle_range = prev_candle["high"] - prev_candle["low"]
    sl_offset = max(0.5 / 100.0 * candle_range, 0.0001)  # 0.5% of prev range, min tick safety

    # Fetch market limits to respect min order size
    mkt = exchange.market(symbol_ccxt)
    amt_min = (mkt.get("limits", {}).get("amount", {}) or {}).get("min", 0.0) or 0.0
    amt_step = (mkt.get("precision", {}) or {}).get("amount", None)

    def _round_amount(a: float) -> float:
        if amt_step is None:
            return float(a)
        # CCXT precision is decimal places, not step size
        return float(round(a, int(amt_step)))

    if signal == "bullish":
        sl_price = current_price - sl_offset
        tp_price = current_price * 1.015  # +1.5%
        risk_per_unit = max(current_price - sl_price, 1e-9)
        qty = max(risk_amount / risk_per_unit, 0.0)
        qty = _round_amount(qty)
        if qty <= 0 or qty < amt_min:
            logger.warning("Position size below exchange minimum; skipping.")
            return
        await place_market_order(exchange, symbol_ccxt, "buy", qty)
        open_positions.append({
            "entry_price": current_price,
            "quantity": qty,
            "side": "long",
            "tp_price": tp_price,
            "sl_price": sl_price,
        })
        logger.info(f"Opened LONG qty={qty} @ {current_price:.4f} TP={tp_price:.4f} SL={sl_price:.4f}")

    elif signal == "bearish":
        sl_price = current_price + sl_offset
        tp_price = current_price * 0.985  # -1.5%
        risk_per_unit = max(sl_price - current_price, 1e-9)
        qty = max(risk_amount / risk_per_unit, 0.0)
        qty = _round_amount(qty)
        if qty <= 0 or qty < amt_min:
            logger.warning("Position size below exchange minimum; skipping.")
            return
        await place_market_order(exchange, symbol_ccxt, "sell", qty)
        open_positions.append({
            "entry_price": current_price,
            "quantity": qty,
            "side": "short",
            "tp_price": tp_price,
            "sl_price": sl_price,
        })
        logger.info(f"Opened SHORT qty={qty} @ {current_price:.4f} TP={tp_price:.4f} SL={sl_price:.4f}")



################################## Main function #####################################################
async def main():
    global last_candle_ts

    exchange = ccxt.binance({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",              # use USDT-M futures
            "adjustForTimeDifference": True,
        },
    })

    try:
        await exchange.load_markets()
        await ensure_leverage(exchange, symbol_ccxt, leverage)
        logger.info("Starting loop… (IST timezone for prints)")

############################################# Data ###########################################
        while True:
            try:
                df = await fetch_last_two_candles(exchange, symbol_ccxt, timeframe)
                print(df.tail(5)) ### see the result
            except Exception as e:
                logger.error(f"Failed to fetch candles: {e}")
                await asyncio.sleep(poll_interval_sec)
                continue

            if df.empty or df.shape[0] < 2:
                await asyncio.sleep(poll_interval_sec)
                continue

###################### Only process when a *new* last candle appears #################################
            latest = df.iloc[-1] #latest candle
            prev = df.iloc[-2]   #pre candle
            if last_candle_ts is not None and latest["ts"] == last_candle_ts: #price is in same candle
                # No new candle yet; just manage open positions on latest price
                await manage_positions(exchange, float(latest["close"]))
                await asyncio.sleep(poll_interval_sec)
                continue

            last_candle_ts = latest["ts"] # Update last_candle_ts with the new candle’s timestamp.

######################### Some Basic Information #####################################################
            change_pct = previous_candle_change_pct(df)
            print(f"%Change in prev_candle:", change_pct)
            signal = get_signal(change_pct)
            print(signal)
            current_price = float(latest["close"])  # we act at the start of the new candle using latest close
            logger.info(
                f"Prev_candle Δ%={change_pct:.3f} | signal={signal} | time(prev)={prev['timestamp']} | time(latest)={latest['timestamp']}"
            )

########################## Balance for sizing ###########################################################
            try:
                bal = await fetch_account_balance(exchange, quote_asset)
                print(f"Balance in you account: " , bal)
            except Exception as e:
                logger.error(f"Could not fetch balance: {e}")
                bal = 0.0


######################## Due to 0 Balance, Not execute trades(I am working on it)########################
            if signal != "neutral" and bal > 0:
                if len(open_positions) == 0:
                    await execute_trade(exchange, signal, current_price, prev.to_dict(), bal)
                else:
                    logger.info("Position already open, skipping new trade")

            # Post-trade risk management on each loop
            await manage_positions(exchange, current_price)

            await asyncio.sleep(poll_interval_sec)

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        await exchange.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting…")








