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
BinanceArb.py: Arbitrage bot for Binance
Logger.py：Logger configuration
detect_spread.py：Spread detection
basis_trading.py：Open/Close positions



3->
->api_key and api_secret in config.py and trading coin
->