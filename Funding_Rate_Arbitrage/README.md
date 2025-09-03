1-> Arbitrage Process
Repeated detection for trading opportunity
Open positions:
    Open long in Spot account
    Universal account transfer：Spot account -> COIN-M Account
    Open short in COIN-M account
Close positions:
    Close short in COIN-M account
    Universal account transfer：COIN-M account -> Spot Account
    Close long in Spot account


2->
Config.py：Account & multiplier information
Logger.py：Logger configuration
detect_spread.py：Spread detection
basis_trading.py：Open/Close positions
BinanceArb.py: Arbitrage bot for Binance



3->
->api_key and api_secret in config.py and trading coin
->


4:->
# Spread detection
python detect_spread.py

# Arbitrage trading
python basis_trading.py --coin 'BTC' --future_date '221230' --amount 1000 --threshold 0.02

# Hyperparameter settings:
    --coin                 Trading Target
    --future_date          expiration date for delivery contract
    --coin_precision       price precision (decimal points)
    --slippage             slippage (proportion of crypto price)
    --spot_fee_rate        commission rate for spot
    --contract_fee_rate    commission rate for contract
    --max_trial            maximum trial for stable connections
    --amount               trading amount for one iteration
    --num_maximum          maximum execution numbers
    --threshold            opening/closing threshold

