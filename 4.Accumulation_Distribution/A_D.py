import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


from sklearn.preprocessing import StandardScaler
# from tensorflow.keras.models import Sequential
# from tensorflow.keras.layers import Dense

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

error_threshold = 0.05


#######################################
open_position = []
scaler = StandardScaler()

# #### Model
# model = Sequential([
#     Dense(16, activation='relu', input_shape=(4,)),
#     Dense(8, activation='relu'),
#     Dense(16, activation='relu'),
#     Dense(4, activation='linear')
# ])
# model.compile(optimizer='adam', loss='mse')


######################################### Data
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
    

############################# Money flow
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df['money_flow_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        df['money_flow_volume']     = df['money_flow_multiplier'] * df['volume']
        df['ad_line']               = df['money_flow_volume'].cumsum()

        ######### atr
        df['tr']  = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(atr_period).mean()

        df['price_change'] = df['close'].pct_change()
        df['ad_change']    = df['ad_line'].pct_change()
        df['volume_change']= df['volume'].pct_change()
        return df
    except Exception as e:
        logger.error(f"Error calculation indicator: {e}")
        return df
    
############################ Model
# def train_model(df: pd.DataFrame) -> None:
#     try:
#         features = ['price_change', 'ad_change', 'atr', 'volume_change']
#         X = df[features].dropna()
#         if len(X) < 10:
#             return
#         X_scaled = scaler.fit_transform(X)
#         model.fit(X_scaled, X_scaled, epochs=50, verbose=0)
#     except Exception as e:
#         logger.error(f"Error train model: {e}")


############# Signal
def get_ad_signal(df: pd.DataFrame)->str:
    try:
        ad_line      = df['ad_line'].iloc[-1]
        ad_line_prev = df['ad_line'].iloc[-2]
        if pd.isna([ad_line, ad_line_prev]).any():
            return 'neutral'
        feature = ['price_change', 'ad_change', 'atr', 'volume_change']
        X = df[feature].iloc[-1:].dropna()
        if X.empty:
            return 'neutral'
        X_scaled = scaler.transform(X)
        X_pred   = model.predict(X_scaled, verbose=0)
        error    = np.mean((X_scaled - X_pred) ** 2)
        
        if ad_line > ad_line_prev and error > error_threshold:
            return 'bullish'
        elif ad_line < ad_line_prev and error > error_threshold:
            return 'bearish'
        return 'neutral'
    except Exception as e:
        logger.error(f"error in signal: {e}")
        return 'neutral'
    
################ position Management 
def position_manage(df: pd.DataFrame)->int:
    try:
        

################################# Main #####################
async def main():
    exchange = ccxt.binance()
    symbol = 'BTC/USDT'
    timeframe = '1m'
    df = await fetch_data(exchange, symbol, timeframe)

    print(df.head())

    await exchange.close()

 
############################
asyncio.run(main())