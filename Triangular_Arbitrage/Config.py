
BINANCE_CONFIG = {
    "apiKey": "Xsbs4NqyjzYf4qTAQAqG68AbKN1yJw9wePUftd1VjITfWil404RbZEDxvrriCk33",
    "secret": "nHNnM7mhcTyslTQThZhD06neCyAahzi0nxW3RlreNpW7NiFj62hMusyLeiERvgmw",
    "timeout": 3000,         # Timeout in ms for API requests (ccxt expects ms not sec)
    "rateLimit": 10,         # Minimum delay (ms) between requests
    "verbose": False,        # Enable debug logging
    "enableRateLimit": True  # Auto respect Binance API limits
}

# Target coins for arbitrage (spot trading pairs)
MULTIPLIER = {
    'BTC/USDT': 100,
    'ETH/USDT': 100,
}

# Base settings
BASE_CURRENCY    = "USDT"
TRADE_AMOUNT     = 100       # Amount to use per arbitrage cycle
FEE_RATE         = 0.001     # Binance spot fee (0.1%)
PROFIT_THRESHOLD = 0.003     # 0.3% minimum profit to trigger execution
POLL_INTERVAL    = 0.2       # REST polling interval (seconds)
