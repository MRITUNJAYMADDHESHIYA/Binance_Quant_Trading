import ccxt
import time
from Logger import get_logger
from Arbitrage import TriangularArbSpot   # if you put your class in a file

if __name__ == "__main__":
    # Initialize exchange with API keys
    exchange = ccxt.binance({
        "apiKey": "$$$$$$$$$$$$$$$$$$$$$$$$$$$",
        "secret": "$$$$$$$$$$$$$$$$$$$$$$",
        "enableRateLimit": True,
        "options": {
            "defaultType": "future"   # ensures futures endpoints
        }
    })

    # Parameters
    threshold   = 0.0001      # 0.1% minimum profit
    amount      = 0.01      # trade size (adjust based on symbol)
    slippage    = 0.000     # 0.05%
    fee_rate    = 0.000    # 0.04% Binance taker fee
    max_trial   = 3          # retry attempts

    # Init bot
    bot = TriangularArbSpot(exchange, threshold, amount, slippage, fee_rate, max_trial)
    logger = get_logger("TriangularArbBot")

    logger.warning("🚀 Starting Triangular Arbitrage Bot on Binance Futures...")

    while True:
        try:
            bot.open_position()   # check arbitrage & place orders if profitable
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
        time.sleep(2)  # wait before next round (tune based on rate limits)
