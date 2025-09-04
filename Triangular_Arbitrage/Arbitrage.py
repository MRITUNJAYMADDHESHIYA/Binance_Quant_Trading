import ccxt
import time
import traceback
from Logger import get_logger

### Spot Market
### Example Cycle: BTCUSDT -> BNBBTC -> BNBUSDT
class TriangularArbSpot:
    def __init__(self, exchange: ccxt.binance, threshold: float, amount: float, slippage: float, fee_rate: float, max_trial: int):
        self.exchange   = exchange
        self.threshold  = threshold           # e.g. 0.001 = 0.1%
        self.amount     = amount              # trade size
        self.slippage   = slippage            # e.g. 0.0005 = 0.05%
        self.fee_rate   = fee_rate            # taker fee ~0.001 (0.1% for spot)
        self.max_trial  = max_trial
        self.logger     = get_logger("Triangular-Spot")

        # Spot market symbols
        self.symbols = {
            "BTCUSDT": "BTCUSDT",  # buy/sell BTC with USDT
            "ETHUSDT": "ETHUSDT",  # buy/sell BNB with USDT
            "ETHBTC":  "ETHBTC"    # buy/sell BNB with BTC
        }

############################Debugging and Error Handling############################ 
    def retry_wrapper(self, func, params=dict(), act_name='', sleep_seconds=1):
        for _ in range(self.max_trial):
            try:
                return func(**params)
            except Exception:
                self.logger.warning(f"{act_name} FAIL. Retrying...")
                self.logger.warning(traceback.format_exc())
                time.sleep(sleep_seconds)
        self.logger.critical(f"{act_name} FAILED too many times")
        return None

############################Place Orders (Spot)############################
    def place_order(self, symbol: str, side: str, amount: float, price: float):
        try:
            order_info = self.retry_wrapper(
                self.exchange.create_order,
                {
                    "symbol": symbol,
                    "type": "limit",
                    "side": side.lower(),  # "buy" or "sell"
                    "price": price,
                    "amount": amount
                },
                act_name=f"Place {side} {symbol}"
            )
            self.logger.info(f"Placed order: {symbol} {side} {amount}@{price}")
            return order_info
        except Exception as e:
            self.logger.error(f"Order failed for {symbol}: {e}")
            return None

######################## Bid/Ask for three symbols #######################################
    def get_prices(self):
        prices = {}
        for sym in self.symbols.values():
            ob = self.retry_wrapper(self.exchange.fetch_order_book, {"symbol": sym}, act_name=f"OrderBook {sym}")
            if ob:
                bid = ob["bids"][0][0]
                ask = ob["asks"][0][0]
                prices[sym] = {"bid": bid, "ask": ask}
        return prices

######################## Check opportunity for placing orders(including fees and slippage) #######################################
    def check_opportunity(self, prices):
        usdt_start = 1.0

        # Cycle A: USDT -> BTC -> ETH -> USDT
        btc_qty = (usdt_start / prices[self.symbols["BTCUSDT"]]["ask"]) * (1 - self.fee_rate - self.slippage)
        eth_qty = (btc_qty / prices[self.symbols["ETHBTC"]]["ask"]) * (1 - self.fee_rate - self.slippage)
        usdt_end_A = (eth_qty * prices[self.symbols["ETHUSDT"]]["bid"]) * (1 - self.fee_rate - self.slippage)
        profit_A = usdt_end_A - usdt_start

        # Cycle B: USDT -> ETH -> BTC -> USDT
        eth_qty = (usdt_start / prices[self.symbols["ETHUSDT"]]["ask"]) * (1 - self.fee_rate - self.slippage)
        btc_qty = (eth_qty * prices[self.symbols["ETHBTC"]]["bid"]) * (1 - self.fee_rate - self.slippage)
        usdt_end_B = (btc_qty * prices[self.symbols["BTCUSDT"]]["bid"]) * (1 - self.fee_rate - self.slippage)
        profit_B = usdt_end_B - usdt_start

        return profit_A, profit_B


################################## Place Orders if Arbitrage Opportunity Found ##################################
    def open_position(self):
        prices = self.get_prices()
        if not prices:
            return

        profit_A, profit_B = self.check_opportunity(prices)

        if profit_A > self.threshold:
            self.logger.warning(f"Cycle A Arbitrage Found! Profit: {profit_A*100:.4f}%")
            # Place orders (USDT->BTC->ETH->USDT)
            self.place_order("BTC/USDT", "BUY", self.amount, prices[self.symbols["BTCUSDT"]]["ask"])
            self.place_order("ETH/BTC", "BUY", self.amount, prices[self.symbols["ETHBTC"]]["ask"])
            self.place_order("ETH/USDT", "SELL", self.amount, prices[self.symbols["ETHUSDT"]]["bid"])

        elif profit_B > self.threshold:
            self.logger.warning(f"Cycle B Arbitrage Found! Profit: {profit_B*100:.4f}%")
            # Place orders (USDT->ETH->BTC->USDT)
            self.place_order("ETH/USDT", "BUY", self.amount, prices[self.symbols["ETHUSDT"]]["ask"])
            self.place_order("ETH/BTC", "SELL", self.amount, prices[self.symbols["ETHBTC"]]["bid"])
            self.place_order("BTC/USDT", "SELL", self.amount, prices[self.symbols["BTCUSDT"]]["bid"])
        else:
            self.logger.info("No arbitrage opportunity found")




########################################### Futures Triangular Arbitrage Class ###########################################
# import ccxt
# import time
# import traceback
# from Logger import get_logger

# ###1.futures market
# ###->BTCUSDT -->ETHBTC -->ETHUSDT
# ###-->buy BTCUSDT
# ###-->buy ETHBTC
# ###-->sell ETHUSDT
# class TriangularArbFutures:
#     def __init__(self, exchange: ccxt.binance, threshold: float, amount: float, slippage: float, fee_rate: float, max_trial: int):
#         self.exchange   = exchange
#         self.threshold  = threshold           # e.g. 0.001 = 0.1%
#         self.amount     = amount              # trade size
#         self.slippage   = slippage            # e.g. 0.0005 = 0.05%
#         self.fee_rate   = fee_rate            # taker fee ~0.0004 (0.04%)
#         self.max_trial  = max_trial
#         self.logger     = get_logger("Triangular-Futures")

#         # Trading pairs for triangular arb
#         self.symbols = {
#             "BTCUSDT": "BTC/USDT:USDT", #buy BTCUSDT
#             "BNBUSDT": "BNB/USDT:USDT", #sell BNBUSDT
#             "BNBBTC": "BNB/BTC:USDT"    #buy BNBBTC
#         }

# ############################Debuging and Error Handling############################ 
#     def retry_wrapper(self, func, params=dict(), act_name='', sleep_seconds=1):
#         for _ in range(self.max_trial):
#             try:
#                 if isinstance(params, dict) and 'timestamp' in params:
#                     params['timestamp'] = int(time.time()) * 1000
#                 return func(**params)
#             except Exception:
#                 self.logger.warning(f"{act_name} FAIL. Retrying...")
#                 self.logger.warning(traceback.format_exc())
#                 time.sleep(sleep_seconds)
#         self.logger.critical(f"{act_name} FAILED too many times")
#         return None

# ############################Place Orders(using limit orders)############################
#     def place_order(self, symbol: str, side: str, amount: float, price: float):
#         params = {
#             "symbol": symbol,
#             "side": side,
#             "type": "LIMIT",
#             "price": price,
#             "quantity": amount,
#             "timeInForce": "GTC",
#         }
#         params['timestamp'] = int(time.time() * 1000)
#         order_info = self.retry_wrapper(self.exchange.fapiPrivatePostOrder, params, act_name=f"Place {side} {symbol}")
#         self.logger.info(f"Placed order: {symbol} {side} {amount}@{price}")
#         return order_info

# ######################## Bid/Ask for three symbols #######################################
#     def get_prices(self):
#         prices = {}
#         for sym in self.symbols.values():
#             ob = self.retry_wrapper(self.exchange.fetch_order_book, {"symbol": sym}, act_name=f"OrderBook {sym}")
#             if ob:
#                 bid = ob["bids"][0][0]
#                 ask = ob["asks"][0][0]
#                 prices[sym] = {"bid": bid, "ask": ask}
#         return prices
    
# ######################## Check opportunity for placing orders(including fees and slippage) #######################################
#     def check_opportunity(self, prices):
#         """
#         Calculate cycle returns for arbitrage
#         """
#         usdt_start = 1.0

#         # Cycle A: USDT -> BTC -> ETH -> USDT
#         btc_qty = (usdt_start / prices[self.symbols["BTCUSDT"]]["ask"]) * (1 - self.fee_rate - self.slippage)
#         eth_qty = (btc_qty * prices[self.symbols["ETHBTC"]]["bid"]) * (1 - self.fee_rate - self.slippage)
#         usdt_end_A = (eth_qty * prices[self.symbols["ETHUSDT"]]["bid"]) * (1 - self.fee_rate - self.slippage)
#         profit_A = usdt_end_A - usdt_start

#         # Cycle B: USDT -> ETH -> BTC -> USDT
#         eth_qty = (usdt_start / prices[self.symbols["ETHUSDT"]]["ask"]) * (1 - self.fee_rate - self.slippage)
#         btc_qty = (eth_qty / prices[self.symbols["ETHBTC"]]["ask"]) * (1 - self.fee_rate -  self.slippage)
#         usdt_end_B = (btc_qty * prices[self.symbols["BTCUSDT"]]["bid"]) * (1 - self.fee_rate - self.slippage)
#         profit_B = usdt_end_B - usdt_start

#         return profit_A, profit_B

# ################################## Place Orders if Arbitrage Opportunity Found ##################################
#     def open_position(self):
#         prices = self.get_prices()
#         if not prices:
#             return

#         profit_A, profit_B = self.check_opportunity(prices)

#         if profit_A > self.threshold:
#             self.logger.warning(f"Cycle A Arbitrage Found! Profit: {profit_A*100:.4f}%")
#             # Place orders (USDT->BTC->ETH->USDT)
#             self.place_order("BTCUSDT", "BUY", self.amount, prices[self.symbols["BTCUSDT"]]["ask"])
#             self.place_order("ETHBTC", "SELL", self.amount, prices[self.symbols["ETHBTC"]]["bid"])
#             self.place_order("ETHUSDT", "SELL", self.amount, prices[self.symbols["ETHUSDT"]]["bid"])

#         elif profit_B > self.threshold:
#             self.logger.warning(f"Cycle B Arbitrage Found! Profit: {profit_B*100:.4f}%")
#             # Place orders (USDT->ETH->BTC->USDT)
#             self.place_order("ETHUSDT", "BUY", self.amount, prices[self.symbols["ETHUSDT"]]["ask"])
#             self.place_order("ETHBTC", "BUY", self.amount, prices[self.symbols["ETHBTC"]]["ask"])
#             self.place_order("BTCUSDT", "SELL", self.amount, prices[self.symbols["BTCUSDT"]]["bid"])
#         else:
#             self.logger.info("No arbitrage opportunity found")



