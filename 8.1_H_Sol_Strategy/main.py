import pandas as pd
import numpy as np
import time
import ccxt
from binance.client import Client

######################## Print method ################
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


################## Global variable ####################
symbol   = 'SOLUSDT'
interval = '1m'
per_change_threshold = 0.01    #percentage change in 1H candle then next candle buy or sell
client = Client('Xsbs4NqyjzYf4qTAQAqG68AbKN1yJw9wePUftd1VjITfWil404RbZEDxvrriCk33', 'nHNnM7mhcTyslTQThZhD06neCyAahzi0nxW3RlreNpW7NiFj62hMusyLeiERvgmw')

######### Position ###########
max_position = 1

######################### Live updating function
def fetch_data(symbol:str, interval: str):
    try:
        candles = client.futures_klines(symbol=symbol, interval=interval, limit=2) #two candle return
        latest = candles[-1] #last candle

        
        start_time = latest[0]
        # Convert to IST
        time_ist = pd.to_datetime(start_time, unit="ms") + pd.Timedelta(hours=5, minutes=30)

        # Build row
        df = pd.DataFrame([{
            "timestamp": time_ist,
            "open": float(latest[1]),
            "high": float(latest[2]),
            "low": float(latest[3]),
            "close": float(latest[4]),
            "volume": float(latest[5])
        }])

        print(f"Updated with new data for {time_ist}")
        print(df.tail(5))
        return df
    except Exception as e:
        print("Error during update:", e)
        return df
    

# ###################################### Testing ################
# if __name__ == "__main__":
#     df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

#     while True:
#         df = fetch_data(symbol='SOLUSDT', interval='1m')
#         time.sleep(5)   # check every 5 seconds (you can change this)

##################### Indicators ####################
def calculate_indicators(df:pd.DataFrame) -> pd.DataFrame:
    try:
        change_per = (df['close'] - df['open'])*100/df['open']


        return change_per
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return change_per
    
##################### Strategy Logic ##########################################
def get_signal(df:pd.DataFrame, change_per: float) -> str:
    try:
        if change_per > per_change_threshold:
            return 'bullish'
        elif change_per < per_change_threshold:
            return 'bearish'
        return 'neutral'
    except Exception as e:
        logger.error(f"Error getting signal: {e}")
        return 'error in signal'
    

########################################## To-Do #########
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
    

########################################## Order placed ########################
async def execute_trade(exchange, signal: str, price: float, prev_candle: dict, account_balance: float):
    try:
        if len(open_positions) >= max_position:
            logger.info("Max position limit reached, skipping trade execution.")
            return

        # Risk management: 3% of account
        risk_amount = account_balance * 0.03  

        # Previous candle size (High - Low)
        candle_range = prev_candle["high"] - prev_candle["low"]
        sl_offset = 0.005 * candle_range  # 0.5% of prev candle range

        if signal == "bullish":
            sl_price = price - sl_offset
            tp_price = price * 1.015  # +1.5% target

            # Position size (qty) based on risk
            risk_per_unit = price - sl_price
            qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0

            if qty <= 0:
                logger.warning("Invalid position size, skipping trade.")
                return

            order = await exchange.create_market_buy_order(symbol, qty)
            open_positions.append({
                "entry_price": price,
                "quantity": qty,
                "side": "long",
                "tp_price": tp_price,
                "sl_price": sl_price
            })
            logger.info(f"Executed LONG at {price}, TP: {tp_price}, SL: {sl_price}, Qty: {qty}")

        elif signal == "bearish":
            sl_price = price + sl_offset
            tp_price = price * 0.985  # -1.5% target

            # Position size (qty) based on risk
            risk_per_unit = sl_price - price
            qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0

            if qty <= 0:
                logger.warning("Invalid position size, skipping trade.")
                return

            order = await exchange.create_market_sell_order(symbol, qty)
            open_positions.append({
                "entry_price": price,
                "quantity": qty,
                "side": "short",
                "tp_price": tp_price,
                "sl_price": sl_price
            })
            logger.info(f"Executed SHORT at {price}, TP: {tp_price}, SL: {sl_price}, Qty: {qty}")

    except Exception as e:
        logger.error(f"Error executing trade: {e}")


######################### main ###################
leverage = 20

async def main():
    try:
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'apiKey': 'Xsbs4NqyjzYf4qTAQAqG68AbKN1yJw9wePUftd1VjITfWil404RbZEDxvrriCk33',
            'secret': 'nHNnM7mhcTyslTQThZhD06neCyAahzi0nxW3RlreNpW7NiFj62hMusyLeiERvgmw',
            'enableLeverage': True,
            'options': {
                'adjustForTimeDifference': True  # ← THIS FIXES THE TIMESTAMP ERROR, then no error in system and server time difference
            }
        })
        await exchange.load_markets()
        await exchange.set_leverage(leverage, symbol)
        # async with websockets.connect(websocket_url) as ws:
        #     logger.info("WebSocket connection established.")     #correct
            
        while True:
            df = await fetch_data(exchange, symbol)
            print(f"Fetched data: {df.tail()}")########## for debugging
            if df.empty:
                logger.warning("No data fetched, retrying...")
                continue
            
           
    
            change_per = calculate_indicators(df)
            print(f"Calculated indicators: {df.tail()}")########## for debugging
            
            if df.empty:
                logger.warning("No data after calculating indicators, retrying...")
                continue
            
            current_price = df['close'].iloc[-1]
            signal = get_signal(df, change_per)
        
            
            if signal != 'neutral':
                await execute_trade(exchange, signal, current_price,)
            
            await manage_position(exchange, current_price)
            
            await asyncio.sleep(check_interval)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        await exchange.close()

# Run the event loop
if __name__ == "__main__":
    asyncio.run(main())
    











