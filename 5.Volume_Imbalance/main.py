import ccxt.async_support as ccxt

import pandas as pd
import numpy as np
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



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
open_position = []
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
        
        df['imbalance'] = 0.0
        if order_book['bids'] and order_book['asks']:
            bid_volume = sum([bid[1] for bid in order_book['bids']])
            ask_volume = sum([ask[1] for ask in order_book['asks']])
            if bid_volume + ask_volume > 0:
                df['imbalance'] = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        return df
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return df
    
######################################