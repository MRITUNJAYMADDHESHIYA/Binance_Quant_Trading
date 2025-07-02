import ccxt
import time
import traceback

from Logger import get_logger

class BinanceArbBot:
    def __init__(self, exchange: ccxt.binance, coin: str, future_date: str, coin_precision: float,
                 slippage:float, spot_fee_rate:float, future_fee_rate:float, multiplier:dict,
                 amount:float, num_maximum:int, threshold:float, max_trial: int):
        self.exchange = exchange
        self.coin = coin
        self.future_date = future_date
        self.coin_precision = coin_precision
        self.slippage = slippage
        self.spot_fee_rate = spot_fee_rate
        self.future_fee_rate = future_fee_rate
        self.multiplier = multiplier
        self.amount = amount
        self.num_maximum = num_maximum
        self.threshold = threshold
        self.max_trial = max_trial
        self.logger = get_logger("Basis-Trading Starts")

        #### depend on symbol name
        self.spot_symbol = {'type1': coin + 'USDT', 'type2': coin + '/USDT'}
        self.future_symbol = {'type1': coin + 'USD_' + future_date}

    
    ### usefull for bot from crasing on temporary issues(example)
        #  price = self.retry_wrapper(
        #     func=self.exchange.fetch_ticker,
        #     params={'symbol': 'BTC/USDT'},
        #     act_name='Fetch BTC Ticker',
        #     sleep_seconds=2
        # )

    def retry_wrapper(self, func, params=dict(), act_name='', sleep_seconds=1, is_exit=True):
        for _ in range(self.max_trial):
            try:
                ### NOTE: reset the local timestamp when requesting again，otherwise requests may be declined
                if isinstance(params, dict) and 'timestamp' in list(params.keys()):
                    params['timestamp'] = int(time.time()) * 1000
                result = func(**params)
                return result
            except Exception as e:
                print('Function parameters:', params)
                self.logger.warning(f"{act_name} ({self.exchange.id}) FAIL | Retry after {sleep_seconds} seconds...")
                self.logger.warning(traceback.format_exc())
                time.sleep(sleep_seconds)
        else:
            self.logger.critical(f"{act_name} FAIL too many times... Arbitrage STOPs!")
            if is_exit: exit()

    def binanace_spot_place_order(self, symbol:str, direction:str, price:float, amount:float):
        if direction == 'long':
            order_info = self.exchange.create_limit_buy_order(symbol, amount, price)
        elif direction == 'short':
            order_info = self.exchange.create_limit_sell_order(symbol, amount, price)
        else:
            raise ValueError('Parameter `direction` supports `long` or `short` only')
        self.logger.debug(f'spot orders ({self.exchange.id}) SUCCESS: {direction}>{amount}>{price}')
        self.logger.debug(f'Order info: {str(order_info)}')

        return order_info
    
    def binance_future_place_order(self, symbol:str, direction:str, price:float, amount:float):
        if direction == 'open_short':
            side = 'SELL'
        elif direction == 'close_short':
            side = 'BUY'
        else:
            raise NotImplemented('Parameter `direction` supports `open_short` or `close_short` only')
        
        ########## POST /dapi/v1/order
        params = {
            'side': side,
            'positionSide': 'SHORT',
            'symbol': symbol,
            'type': 'LIMIT',
            'price': price,
            'quantity': amount,
            'timeInForce': 'GTC',
        }

        params['timestamp'] = int(time.time() * 1000) #milliseconds
        order_info = self.exchange.dapiPrivatePostOrder(params)
        self.logger.debug(f'({self.exchange.id}) Future orders SUCCESS: {direction}>{symbol}>{amount}>{price}')
        self.logger.debug(f'Order info: {str(order_info)}')

        return order_info
    
    def binance_account_transfer(self, currency:str, amount, from_account='spot', to_account='coin-margin'):

        if from_account == 'spot' and to_account == 'coin-margin':
            transfer_type = 'MAIN_CMFUTURE'
        elif from_account == 'coin-margin' and to_account == 'spot':
            transfer_type = 'CMFUTURE_MAIN'
        else:
            raise ValueError('Cannot recognize parameters for Use Universal Transfer')
        
        ######## POST /sapi/v1/asset/transfer
        params = {
            'asset': currency,
            'amount': amount,
            'type'  : transfer_type,
        }

        params['timestamp'] = int(time.time() * 1000)  # milliseconds
        transfer_info = self.exchange.sapiPostAssetTransfer(params)
        self.logger.debug(f'({self.exchange.id}) Transfer SUCCESS: {from_account} to {to_account} {currency} {amount}')
        self.logger.debug(f'Transfer info: {str(transfer_info)}')

        return transfer_info
    

    def open_position(self):
        execute_num = 0

        while True:
            spot_ask1 = self.exchange.publicGetTickerBookTicker(params={'symbol': self.spot_symbol['type1']})['askPrice']
            coin_bid1 = self.exchange.dapiPublicGetTickerBookTicker(params={'symbol': self.future_symbol['type1']})[0]['bidPrice']

            r = float(coin_bid1)/float(spot_ask1) - 1
            operator = '>' if spot_ask1 > coin_bid1 else '<'
            self.logger.info('Spot %.4f %s COIN-M %.4f -> Price Difference: %.4f%%' % (float(spot_ask1), operator, float(coin_bid1), r * 100))

            if r < self.threshold:
                self.logger.info('Price difference Smaller than threshold >>> Retying....')
            else:
                self.logger.debug('Price difference Larger than threshold >>> Start to open position')

                contract_num      = int(self.amount / self.multipler[self.coin])
                contract_coin_num = contract_num * self.multiplier[self.coin]/float(coin_bid1)
                contract_fee      = contract_coin_num * self.contract_fee_rate
                spot_amount       = contract_coin_num / (1-self.spot_fee_rate) + contract_fee
                self.logger.debug(f'Arbitrage starts >>> future contract num {contract_num} > coin-margin num {contract_coin_num} > fee {contract_fee} > spot amount {spot_amount}')

                price = float(spot_ask1) * (1 + self.slippage)
                params = {
                    'symbol' : self.spot_symbol
                }