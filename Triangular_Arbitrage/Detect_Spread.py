import ccxt
import pandas as pd
import time

from Logger import get_logger
from Config import BINANCE_CONFIG


class SpreadDetector(ccxt.binance):
    def __init__(self):
        super().__init__(BINANCE_CONFIG)
        self.time_interval = 1  # seconds
        self.symbols = ["BTC/USDT", "ETH/USDT", "ETH/BTC"]

    def get_spread_info(self, logger):
        spread_data = []

        for sym in self.symbols:
            try:
                #convert "BTC/USDT" -> "BTCUSDT" for Binance API
                sym_api = sym.replace("/", "")

                ticker = self.publicGetTickerBookTicker(params={"symbol": sym_api})
                bid = float(ticker["bidPrice"])
                ask = float(ticker["askPrice"])

                #open_spread = buy at ask, sell at bid
                open_spread = (ask / bid) - 1

                #close_spread = sell at bid, buy at ask
                close_spread = (bid / ask) - 1

                spread_data.append((sym, round(bid, 6), round(ask, 6), round(open_spread * 100, 6), round(close_spread * 100, 6),))

            except Exception as e:
                logger.error(f"Error fetching {sym}: {e}")

        df = pd.DataFrame(
            spread_data,
            columns=["symbol", "bid", "ask", "open_spread(%)", "close_spread(%)"],
        )
        print(df.to_string(index=False))
        return df


if __name__ == "__main__":
    exchange = SpreadDetector()
    LOGGER = get_logger("Spread Detection")
    while True:
        LOGGER.warning("New round for spread detection")
        exchange.get_spread_info(logger=LOGGER)
        time.sleep(exchange.time_interval)
