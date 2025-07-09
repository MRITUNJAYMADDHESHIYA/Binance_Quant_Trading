import ccxt.async_support as ccxt
import asyncio
import websockets
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


### list, array, if/else, for/while
#######################################
symbol = 'ALCH/USDT'
timeframe = '1m'
risk_amount = 10.0
leverage    = 5
atr_period  = 14
tp_multiplier = 2.0
sl_multiplier = 1.0
fee_rate      = 0.0002
max_position  = 2
check_interval = 0.1

imbalance_threshold = 0.05
websocket_url = 'wss://stream.binance.com/ws/alchusdt@depth10@100ms'

DELTA_FACTOR = 0.5  # Factor to adjust delta based on ATR

open_positions = []
###################################
async def fetch_data(exchange, symbol:str, timeframe:str, limit:int=100)->pd.DataFrame:
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return pd.DataFrame() 
    
##########################################
async def fetch_order_book(exchange, symbol: str) -> dict:
    try:
        order_book = await exchange.fetch_order_book(symbol, limit=10)
        return order_book
    except Exception as e:
        logger.error(f"Error fetching order book: {e}")
        return {'bids': [], 'asks': []}
    
###########################################
def calculate_indicators(df:pd.DataFrame, order_book: dict) -> pd.DataFrame:
    try:
        df['tr'] = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift()).abs(),
            (df['low'] - df['close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(window=atr_period).mean()
        
        bid_best   = max(bid[0] for bid in order_book['bids']) if order_book['bids'] else 0
        ask_best   = min(ask[0] for ask in order_book['asks']) if order_book['asks'] else 0
        fair_price = (bid_best + ask_best) / 2 if (bid_best + ask_best) > 0 else 0
        delta      = DELTA_FACTOR * df['atr'].iloc[-1] if not df.empty else 0
        return df, bid_best, ask_best, fair_price, delta
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return df, 0.0, float('inf'), 0.0, 0.0
    
###################################### Strategy Logic ##########################################
def get_arbitrage_signal(bid: float, ask: float, fair_price: float, delta:float) ->str:
    try:
        if bid > fair_price + delta:
            return 'bullish'
        elif ask < fair_price - delta:
            return 'bearish'
        return 'neutral'
    except Exception as e:
        logger.error(f"Error getting imbalance signal: {e}")
        return 'neutral'
    
##########################################
async def manage_position(exchange, current_price: float):
    global open_positions
    positions_to_remove = []
    try:
        for pos in open_positions:
            entry_price = pos['entry_price']
            qty = pos['quantity']
            side = pos['side']
            tp_price = pos['tp_price']
            sl_price = pos['sl_price']
            if side == 'long':
                if current_price >= tp_price:
                    logger.info(f"Taking profit for long position at {tp_price}")
                    await exchange.create_market_sell_order(symbol, qty)
                    positions_to_remove.append(pos)
                elif current_price <= sl_price:
                    logger.info(f"stop loss for long position at {sl_price}")
                    await exchange.create_market_sell_order(symbol, qty)
                    positions_to_remove.append(pos)
            else:
                if current_price <= tp_price:
                    logger.info("Taking profit for short position at {tp_price}")
                    await exchange.create_market_buy_order(symbol, qty)
                    positions_to_remove.append(pos)
                elif current_price >= sl_price:
                    logger.info(f"Stop loss for short position at {sl_price}")
                    await exchange.create_market_buy_order(symbol, qty)
                    positions_to_remove.append(pos)
        open_positions = [pos for pos in open_positions if pos not in positions_to_remove]

    except Exception as e:
        logger.error(f"Error managing positions: {e}")
        return 
 
##########################################
async def execute_trade(exchange, signal: str, price: float, atr: float):
    try:
        if len(open_positions) >= max_position:
            logger.info("Max position limit reached, skipping trade execution.")
            return
        
        qty = risk_amount / price 
        if signal == 'bullish':
            tp_price = price + (tp_multiplier * atr)
            sl_price = price - (sl_multiplier * atr)
            order = await exchange.create_market_buy_order(symbol, qty)
            open_positions.append({
                'entry_price': price,
                'quantity': qty,
                'side': 'long',
                'tp_price': tp_price,
                'sl_price': sl_price
            })
            logger.info(f"Executed long trade at {price}, TP: {tp_price}, SL: {sl_price}")
        elif signal == 'bearish':
            tp_price = price - (tp_multiplier * atr)
            sl_price = price + (sl_multiplier * atr)
            order = await exchange.create_market_sell_order(symbol, qty)
            open_positions.append({
                'entry_price': price,
                'quantity': qty,
                'side': 'short',
                'tp_price': tp_price,
                'sl_price': sl_price
            })
            logger.info(f"Executed short trade at {price}, TP: {tp_price}, SL: {sl_price}")
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        

##########################################
async def main():
    try:
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'apiKey': '*************',
            'secret': '************',
            'enableLeverage': True,

        })
        await exchange.load_markets()
        await exchange.set_leverage(leverage, symbol)
        async with websockets.connect(websocket_url) as ws:
            logger.info("WebSocket connection established.")     #correct
            
        while True:
            df = await fetch_data(exchange, symbol, timeframe)
            print(f"Fetched data: {df.tail()}")########## for debugging
            if df.empty:
                logger.warning("No data fetched, retrying...")
                continue
            
            order_book = await fetch_order_book(exchange, symbol)
            print(f"Fetched order book: {order_book}")########## for debugging
            df, bid, ask, fair_price, delta = calculate_indicators(df, order_book)
            print(f"Calculated indicators: {df.tail()}")########## for debugging
            
            if df.empty:
                logger.warning("No data after calculating indicators, retrying...")
                continue
            
            current_price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]
            signal = get_arbitrage_signal(bid, ask, fair_price, delta)
        
            
            if signal != 'neutral':
                await execute_trade(exchange, signal, current_price, atr)
            
            await manage_position(exchange, current_price)
            
            await asyncio.sleep(check_interval)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")


# Run the event loop
if __name__ == "__main__":
    asyncio.run(main())