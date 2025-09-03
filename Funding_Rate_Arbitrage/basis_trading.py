# Open/Close position
import argparse
import ccxt

from Config import *
from BinanceArb import BinanceArbBot


def init_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exchange', type=str, default='binance', help='exchange name')
    parser.add_argument('--coin', type=str, default='ADA', help='coin symbol')
    parser.add_argument('--future_date', type=str, default='221230', help='expiration date')
    parser.add_argument('--coin_precision', type=int, default=5, help="price precision")
    parser.add_argument('--slippage', type=float, default=0.02, help="proportion of coin price")

    # Use set_defaults for dicts
    parser.set_defaults(multiplier=multiplier)

    # Fees
    parser.add_argument('--spot_fee_rate', type=float, default=1/1000, help="spot fee rate")
    parser.add_argument('--contract_fee_rate', type=float, default=1/10000, help="future contract fee rate")
    parser.add_argument('--max_trial', type=int, default=5, help="number of trials for connection")

    return parser


if __name__ == '__main__':

    # ***open positions***
    position_parser = init_argparse()
    position_parser.add_argument('--amount', type=float, default=20.0, help="spot trading amount for one iteration")
    position_parser.add_argument('--num_maximum', type=int, default=3, help="maximum execution numbers")
    position_parser.add_argument('-f', '--threshold', type=float, default=0.025, help="opening threshold")
    args = position_parser.parse_args()

    # build exchange
    exchange = getattr(ccxt, args.exchange)(BINANCE_CONFIG)

    #trading_bot = BinanceArbBot(exchange=exchange, **vars(args))
    trading_bot = BinanceArbBot(**vars(args))
    trading_bot.open_position()

    # ***close positions***
    # position_parser = init_argparse()
    # position_parser.add_argument('--amount', type=float, default=10.0, help="number of coins for one iteration")
    # position_parser.add_argument('--num_maximum', type=int, default=3, help="maximum execution numbers")
    # position_parser.add_argument('--threshold', type=float, default=0.0005, help="closing threshold")
    # args = position_parser.parse_args()
    #
    # exchange = getattr(ccxt, args.exchange)(BINANCE_CONFIG)
    # trading_bot = BinanceArbBot(exchange=exchange, **vars(args))
    # trading_bot.close_position()
