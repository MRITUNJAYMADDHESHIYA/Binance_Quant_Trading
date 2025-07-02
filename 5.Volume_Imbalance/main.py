import asyncio
import ccxt.async_support as ccxt
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
check_interval = 60

imbalance_threshold = 0.05
websocket_url = 'wss://stream.binance.com/ws/alchusdt@depth10@100ms'

########################################
open_positions = []
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
        
        bid_volume = sum([bid[1] for bid in order_book['bids']])
        ask_volume = sum([ask[1] for ask in order_book['asks']])
        imbalance  = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
        return df, imbalance
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return df, 0.0
    
######################################
def get_imbalance_signal(imbalance: float) ->str:
    try:
        if imbalance > imbalance_threshold:
            return 'bullish'
        elif imbalance < -imbalance_threshold:
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
                    logger.ifo("Taking profit for short position at {tp_price}")
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
            'apiKey': 'Xsbs4NqyjzYf4qTAQAqG68AbKN1yJw9wePUftd1VjITfWil404RbZEDxvrriCk33',
            'secret': 'nHNnM7mhcTyslTQThZhD06neCyAahzi0nxW3RlreNpW7NiFj62hMusyLeiERvgmw',
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
            df, imbalance = calculate_indicators(df, order_book)
            print(f"Calculated indicators: {df.tail()}")########## for debugging
            
            if df.empty:
                logger.warning("No data after calculating indicators, retrying...")
                continue
            
            current_price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]
            signal = get_imbalance_signal(imbalance)
        
            
            if signal != 'neutral':
                await execute_trade(exchange, signal, current_price, atr)
            
            await manage_position(exchange, current_price)
            
            await asyncio.sleep(check_interval)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")


# Run the event loop
if __name__ == "__main__":
    asyncio.run(main())