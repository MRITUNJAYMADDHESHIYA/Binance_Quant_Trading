import ccxt
import time
import math
import traceback

from Logger import get_logger


class BinanceTriArbBot:
    def __init__(self, exchange: ccxt.binance, base: str = "USDT", coin_a: str = "BTC", coin_b: str = "ETH", fee_rate: float = 0.001, slippage: float = 0.0005, start_amount_base: float = 100.0, threshold: float = 0.0015, max_trial: int = 5 ):
        self.exchange = exchange
        self.base = base.upper()      #USDT
        self.coin_a = coin_a.upper()  #BTC
        self.coin_b = coin_b.upper()  #ETH
        self.fee_rate = fee_rate      #0.1% per trade
        self.slippage = slippage      #0.05% slippage buffer per trade
        self.start_amount_base = start_amount_base #100 USDT
        self.threshold = threshold    #0.15% minimum net spread to execute
        self.max_trial = max_trial    #max retries for API calls
        self.logger = get_logger("Triangular-Arbitrage")

        # Load markets once, used for precision and symbol existence
        self.markets = self.retry_wrapper(func=self.exchange.load_markets, params={}, act_name="Load markets", sleep_seconds=1, is_exit=True)
        self.time_interval = 1  # polling interval seconds


    def retry_wrapper(self, func, params=dict(), act_name='', sleep_seconds=1, is_exit=True):
        for _ in range(self.max_trial):
            try:
                if isinstance(params, dict) and 'timestamp' in params:
                    params['timestamp'] = int(time.time()) * 1000
                result = func(**params)
                return result
            except Exception:
                self.logger.warning(f"{act_name} ({self.exchange.id}) FAIL | Retry after {sleep_seconds} seconds...")
                self.logger.warning(traceback.format_exc())
                time.sleep(sleep_seconds)
        else:
            self.logger.critical(f"{act_name} FAIL too many times... Bot STOPs!")
            if is_exit:
                exit()

    def _exists(self, sym: str) -> bool:
        return sym in self.markets

    def _book_ticker(self, sym: str):
        """Use raw REST for speed, return (bid, ask) floats."""
        # Convert 'BTC/USDT' -> 'BTCUSDT' for raw endpoint
        sym_api = sym.replace('/', '')
        data = self.retry_wrapper(
            func=self.exchange.publicGetTickerBookTicker,
            params={'params': {'symbol': sym_api}},
            act_name=f"BookTicker {sym}",
            sleep_seconds=0.2,
            is_exit=False
        )
        # Some symbols return list; most return dict
        if isinstance(data, list):
            data = data[0]
        bid = float(data["bidPrice"])
        ask = float(data["askPrice"])
        return bid, ask

    def _price_for(self, base: str, quote: str):
        """
        Return (bid, ask, direct) where direct=+1 if base/quote exists,
        else use quote/base and invert with direct=-1.

        bid/ask semantics returned:
          - If direct (base/quote): we return its (bid, ask).
          - If inverted (quote/base): we compute:
                bid = 1/ask(quote/base)
                ask = 1/bid(quote/base)
        """
        direct = f"{base}/{quote}"
        inverse = f"{quote}/{base}"

        if self._exists(direct):
            bid, ask = self._book_ticker(direct)
            return bid, ask, +1

        if self._exists(inverse):
            ibid, iask = self._book_ticker(inverse)
            # invert
            bid = 1.0 / iask
            ask = 1.0 / ibid
            return bid, ask, -1

        raise ValueError(f"No market for {base}/{quote} or {quote}/{base}")

    def _round_amount(self, symbol: str, amount: float) -> float:
        """
        Round amount to market's base precision & min amount.
        """
        market = self.markets.get(symbol)
        if not market:
            return amount
        # base precision
        p = market.get('precision', {}).get('amount')
        if p is not None:
            amount = float(f"{amount:.{p}f}")
        # min amount
        limits = market.get('limits', {}).get('amount', {})
        min_amt = limits.get('min')
        if min_amt is not None and amount < min_amt:
            # bump to min if too small (caller should check balances as well)
            amount = min_amt
        return amount

    # -----------------------
    # Spread / Opportunity
    # -----------------------

    def _simulate_cycle(self, direction="A-first"):
        """
        Returns dict with:
          {
            'direction': 'A-first' or 'B-first',
            'start_base': float,
            'final_base': float,
            'net_spread': float (decimal),  # e.g., 0.002 = +0.2%
            'legs': [
                {'pair': 'X/Y', 'side': 'buy/sell', 'px_used': float, 'qty_in': float, 'qty_out': float}
            ]
          }
        Computation uses bid/ask and applies fee & slippage buffer per leg.
        """
        BASE = self.base
        A    = self.coin_a
        B    = self.coin_b

        # Step mapping per direction:
        # A-first: BASE -> A -> B -> BASE
        # B-first: BASE -> B -> A -> BASE
        path = []
        if direction == "A-first":
            path = [(A, BASE), (B, A), (BASE, B)]
        else:
            path = [(B, BASE), (A, B), (BASE, A)]

        amount_base = self.start_amount_base
        legs = []

        for idx, (out_coin, in_coin) in enumerate(path):
            # out_coin/in_coin means we want the price of out_coin quoted in in_coin
            # Example: (BTC, USDT) -> BTC/USDT
            bid, ask, direct = self._price_for(out_coin, in_coin)

            # Decide whether the user is BUYING the base of the pair (out_coin) or SELLING it
            # If we hold 'in_coin' and want 'out_coin', we're BUYING out_coin at ASK.
            # If we hold 'out_coin' and want 'in_coin', we'd SELL out_coin at BID.
            #
            # Leg 1:
            #   holding in_coin (BASE), want out_coin (A or B) => BUY at ask
            # Leg 2:
            #   holding previous out_coin, want next out_coin => depends on mapping
            #   In our mapping we always hold the 'in_coin' and want 'out_coin', so BUY at ask
            # Leg 3:
            #   holding B (or A) and want BASE => SELL at bid *in pair BASE/out_coin*, but our function
            #   ensures bid/ask reflect out_coin/in_coin appropriately. To stay consistent, we keep the same rule:
            #   We always model "we hold in_coin and want out_coin" => BUY out_coin with in_coin at ASK price.
            #
            # So we treat each leg as a BUY of 'out_coin' using 'in_coin' at ASK (pay fees).
            # For the last leg, out_coin will be BASE, and in_coin will be B (or A), so BUY BASE with B at its ASK.
            #
            # Quantity math:
            #   qty_out_coin = qty_in_coin / price_ask
            #
            # Apply slippage (worse price) and fee.

            # Figure how much we have of in_coin for this leg:
            if idx == 0:
                qty_in = amount_base  # in BASE
            else:
                # qty_in is whatever we received from previous leg, denominated in 'in_coin'
                qty_in = legs[-1]['qty_out']

            px_used = ask * (1 + self.slippage)  # pessimistic execution
            qty_out = (qty_in / px_used) * (1 - self.fee_rate)

            legs.append({
                'pair': f"{out_coin}/{in_coin}" if direct == +1 else f"{in_coin}/{out_coin} (inv.)",
                'side': 'buy',
                'px_used': px_used,
                'qty_in': qty_in,
                'qty_out': qty_out,
                'note': 'ASK with slippage, fee applied'
            })

        final_base = legs[-1]['qty_out']  # After last leg, we should be in BASE
        net_spread = (final_base / self.start_amount_base) - 1.0

        return {
            'direction': direction,
            'start_base': self.start_amount_base,
            'final_base': final_base,
            'net_spread': net_spread,
            'legs': legs,
        }

    def detect_once(self):
        """Compute spreads for both directions and return the better one."""
        a_first = self._simulate_cycle("A-first")
        b_first = self._simulate_cycle("B-first")

        best = a_first if a_first['net_spread'] >= b_first['net_spread'] else b_first
        self.logger.info(
            f"Cycle {best['direction']} | Net Spread: {best['net_spread']*100:.4f}% "
            f"(start {best['start_base']} {self.base} -> final {best['final_base']:.6f} {self.base})"
        )
        return best

    # -----------------------
    # Execution
    # -----------------------

    def _market_buy(self, symbol: str, base_ccy: str, quote_ccy: str, spend_quote: float, px_ask: float):
        """
        Market BUY base_ccy/quote_ccy by specifying amount of base to acquire,
        derived from spend_quote at worst price (px_ask * (1+slippage)).
        """
        # amount is in BASE of that symbol (CCXT rule)
        # base_to_buy = spend_quote / px_ask
        base_to_buy = spend_quote / px_ask
        base_to_buy = self._round_amount(symbol, base_to_buy)
        order = self.retry_wrapper(
            func=self.exchange.create_order,
            params={
                'symbol': symbol,
                'type': 'market',
                'side': 'buy',
                'amount': base_to_buy
            },
            act_name=f"Market BUY {symbol}",
            sleep_seconds=0.2,
            is_exit=False
        )
        return order, base_to_buy

    def _market_sell(self, symbol: str, base_ccy: str, amount_base: float):
        """
        Market SELL base_ccy/quote_ccy for amount of base (CCXT rule).
        """
        amt = self._round_amount(symbol, amount_base)
        order = self.retry_wrapper(
            func=self.exchange.create_order,
            params={
                'symbol': symbol,
                'type': 'market',
                'side': 'sell',
                'amount': amt
            },
            act_name=f"Market SELL {symbol}",
            sleep_seconds=0.2,
            is_exit=False
        )
        return order, amt

    def _resolve_symbol(self, base_ccy: str, quote_ccy: str) -> (str, int):
        """
        Return (symbol, direct) where direct=+1 if base/quote exists, else use quote/base with direct=-1.
        """
        direct = f"{base_ccy}/{quote_ccy}"
        inverse = f"{quote_ccy}/{base_ccy}"
        if self._exists(direct):
            return direct, +1
        if self._exists(inverse):
            return inverse, -1
        raise ValueError(f"No market for {base_ccy}/{quote_ccy} or {quote_ccy}/{base_ccy}")

    def execute_cycle(self, plan: dict):
        """
        Execute the 3 market orders following the simulated 'plan'.
        Plan assumes BUY at ASK each leg. We’ll reproduce that with market orders.
        """
        if plan['net_spread'] < self.threshold:
            self.logger.info(
                f"Net spread {plan['net_spread']*100:.4f}% < threshold {self.threshold*100:.2f}% | Skip."
            )
            return False

        self.logger.info(f"Executing cycle: {plan['direction']} (expected {plan['net_spread']*100:.4f}%)")

        try:
            # Leg 1
            leg1 = plan['legs'][0]
            out1, in1 = self._parse_pair_label(leg1['pair'])
            sym1, dir1 = self._resolve_symbol(out1, in1)
            bid1, ask1 = self._book_ticker(sym1)
            px1 = ask1 * (1 + self.slippage)
            # Spend the qty_in (in1)
            spend_quote = leg1['qty_in']  # in in1 currency
            if dir1 == -1:
                # If using inverse symbol, sym1 = in1/out1, market BUY base=in1 using out1
                # but we want to acquire 'out1' spending 'in1'. With inverse symbol we can:
                # - place a MARKET SELL of base=in1? That flips logic.
                # To keep consistent, when inverse we’ll recompute spend on the direct symbol string.
                # Simpler: always call execution on the symbol in base/quote as returned by _resolve_symbol.
                # For BUY semantics we want to acquire the BASE of 'sym1'.
                # If sym1 == in1/out1, to acquire 'out1' we must SELL 'in1' -> which is a 'sell' on sym1.
                # So we switch to SELL path when dir=-1.
                # SELL amount_base = spend_quote (in base of sym1 = in1) /just convert spend to base amount/
                # For market SELL we specify amount of base (in1) to sell:
                order1, sold_amt = self._market_sell(sym1, base_ccy=in1, amount_base=spend_quote)
                got_quote = sold_amt * bid1 * (1 - self.fee_rate)  # we sold base at bid into quote (out1)
                qty_out_leg1 = got_quote  # this is amount of 'out1'
            else:
                # direct symbol out1/in1: BUY out1 with in1
                order1, bought_amt = self._market_buy(sym1, base_ccy=out1, quote_ccy=in1, spend_quote=spend_quote, px_ask=px1)
                qty_out_leg1 = bought_amt  # received out1

            # Leg 2
            leg2 = plan['legs'][1]
            out2, in2 = self._parse_pair_label(leg2['pair'])
            sym2, dir2 = self._resolve_symbol(out2, in2)
            bid2, ask2 = self._book_ticker(sym2)
            px2 = ask2 * (1 + self.slippage)

            # We hold in2 (from leg1 result == out1); ensure mapping:
            hold_ccy = in2
            if hold_ccy != out1 and hold_ccy != self.coin_b and hold_ccy != self.coin_a:
                self.logger.warning("Currency continuity mismatch on leg 2; aborting.")
                return False

            spend_quote2 = qty_out_leg1  # in currency 'in2'
            if dir2 == -1:
                # sym2 = in2/out2, to acquire out2 we SELL in2
                order2, sold_amt2 = self._market_sell(sym2, base_ccy=in2, amount_base=spend_quote2)
                got_quote2 = sold_amt2 * bid2 * (1 - self.fee_rate)  # into out2
                qty_out_leg2 = got_quote2
            else:
                # direct out2/in2: BUY out2 using in2
                order2, bought_amt2 = self._market_buy(sym2, base_ccy=out2, quote_ccy=in2, spend_quote=spend_quote2, px_ask=px2)
                qty_out_leg2 = bought_amt2

            # Leg 3
            leg3 = plan['legs'][2]
            out3, in3 = self._parse_pair_label(leg3['pair'])
            sym3, dir3 = self._resolve_symbol(out3, in3)
            bid3, ask3 = self._book_ticker(sym3)
            px3 = ask3 * (1 + self.slippage)

            spend_quote3 = qty_out_leg2  # denominated in in3
            if dir3 == -1:
                # sym3 = in3/out3, to acquire out3 we SELL in3
                order3, sold_amt3 = self._market_sell(sym3, base_ccy=in3, amount_base=spend_quote3)
                got_quote3 = sold_amt3 * bid3 * (1 - self.fee_rate)  # into out3 (BASE)
                final_base = got_quote3
            else:
                # direct out3/in3: BUY out3 using in3 (out3 should be BASE)
                order3, bought_amt3 = self._market_buy(sym3, base_ccy=out3, quote_ccy=in3, spend_quote=spend_quote3, px_ask=px3)
                final_base = bought_amt3

            realized = (final_base / self.start_amount_base) - 1.0
            self.logger.info(f"Executed cycle {plan['direction']} | Realized: {realized*100:.4f}% "
                             f"({self.start_amount_base} {self.base} -> {final_base:.6f} {self.base})")
            return True

        except Exception:
            self.logger.error("Execution failed:")
            self.logger.error(traceback.format_exc())
            return False

    def _parse_pair_label(self, label: str):
        """Extract coins from leg['pair'] which may be 'X/Y' or 'Y/X (inv.)'"""
        if '(inv.)' in label:
            label = label.split()[0]
        a, b = label.split('/')
        return a, b

    # -----------------------
    # Main loop
    # -----------------------

    def run(self):
        while True:
            self.logger.warning("New round for triangular arbitrage detection")
            plan = self.detect_once()
            # Execute only if profitable beyond threshold
            self.execute_cycle(plan)
            time.sleep(self.time_interval)


# -----------------------
# Example bootstrap
# -----------------------
if __name__ == "__main__":
    # ccxt binance (spot)
    exchange = ccxt.binance({
        "apiKey": "",   # fill in or use only public endpoints for detection
        "secret": "",
        "enableRateLimit": True,
        "timeout": 3000
    })

    bot = BinanceTriArbBot(
        exchange=exchange,
        base="USDT",
        coin_a="BTC",
        coin_b="ETH",
        fee_rate=0.001,          # adjust if you have BNB fee discount
        slippage=0.0005,         # 5 bps
        start_amount_base=100,   # use 100 USDT per cycle
        threshold=0.0015,        # 0.15% net
        max_trial=5
    )
    bot.run()
