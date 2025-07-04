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


open_positions = []
async def fetch_data(exchange, symbol:str, timeframe:str, limit:int=100)->pd.Data:
    