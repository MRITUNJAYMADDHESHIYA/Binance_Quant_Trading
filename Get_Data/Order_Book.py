import asyncio
import websockets
import json
import pandas as pd
from datetime import datetime, timezone, timedelta

############################ Local timezone(UTC+5:30) #####################################
IST = timezone(timedelta(hours=5, minutes=30))

############################ URL for Binance WebSocket API #################################
symbol = "btcusdt"
url = f"wss://stream.binance.com:9443/ws/{symbol}@bookTicker"
url1 = f"wss://stream.binance.com:9443/ws/{symbol}@avgPrice"
levels = 5  # Top 5 bids and asks
url2 = f"wss://stream.binance.com:9443/ws/{symbol}@depth{levels}@100ms"
url3 = f"wss://stream.binance.com:9443/ws/btcusdt@klines_1s"
url4 = f"wss://stream.binance.com:9443/ws/{symbol}@aggTrade"


############################ BookTicker (Single symbol best bid/ask) #########################################
async def best_bid_ask():
    global seq
    data = []
    seq = 0
    async with websockets.connect(url) as ws:
        while True:
            msg = await ws.recv()
            msg = json.loads(msg)
            seq += 1
            now = datetime.now(IST) 

            data.append({
                "seq": seq,
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "bid_price": float(msg["b"]),
                "bid_size": float(msg["B"]),
                "ask_price": float(msg["a"]),
                "ask_size": float(msg["A"])
            })

            if seq % 100 == 0:
                df = pd.DataFrame(data)
                df.to_csv("best_bid_ask.csv", index=False)
                print(f"Saved {len(data)} rows (last time {now})")

# asyncio.run(best_bid_ask())


############################ Avg Price in a time interval #########################################
interval = "5s"  # 5s interval avg. price
async def collect_avgprice():
    global seq
    data = []
    seq = 0
    async with websockets.connect(url1) as ws:
        while True:
            msg = await ws.recv()
            msg = json.loads(msg)
            seq += 1
            now = datetime.now(IST)
            

            data.append({
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "seq": seq,
                "avg_price": float(msg["w"]),
                "interval": msg["i"]
            })

            # Save every 60 events (~1 min)
            if seq % 60 == 0:
                df = pd.DataFrame(data)
                df.to_csv("avg_price.csv", index=False)
                print(f"Saved {len(data)} rows (last avg {msg['w']} at {now})")

#asyncio.run(collect_avgprice())

############################### Top <levels> bids and asks, pushed every second. #########################################
async def collect_depth():
    data = []
    seq = 0
    async with websockets.connect(url2) as ws:
        print(f"Connected to {symbol.upper()} depth{levels} stream (100ms)...")
        while True:
            msg = await ws.recv()
            msg = json.loads(msg)
            seq += 1
            now = datetime.now(IST)

            bids = msg["bids"]  # list of [price, qty]
            asks = msg["asks"]

            # Take best bid/ask (level 1)
            best_bid_price, best_bid_qty = map(float, bids[0])
            best_ask_price, best_ask_qty = map(float, asks[0])

            data.append({
                "seq": seq,
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "best_bid_price": best_bid_price,
                "best_bid_qty": best_bid_qty,
                "best_ask_price": best_ask_price,
                "best_ask_qty": best_ask_qty
            })

            # Save every 100 events (~10 sec at 100ms interval)
            if seq % 100 == 0:
                df = pd.DataFrame(data)
                df.to_csv("orderbook_depth.csv", index=False)
                print(f"Saved {len(data)} rows (last bid {best_bid_price}, ask {best_ask_price} at {now})")

#asyncio.run(collect_depth())

################################ Candlestick data (1 min) #########################################
timeframe = "1s"
async def collect_kline():
    data = []
    seq = 0
    async with websockets.connect(url3) as ws:
        print(f"Connected to {symbol.upper()} {timeframe} kline stream...")
        while True:
            msg = await ws.recv()
            msg = json.loads(msg)
            k = msg["k"]
            seq += 1
            now = datetime.now(IST)

            data.append({
                "seq": seq,
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "kline_start": datetime.fromtimestamp(k["t"]/1000, IST).strftime("%Y-%m-%d %H:%M:%S"),
                "kline_close": datetime.fromtimestamp(k["T"]/1000, IST).strftime("%Y-%m-%d %H:%M:%S"),
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
                "trades": k["n"],
                "is_closed": k["x"]  # True when candle is finished
            })

            # Save every 50 messages (~depends on candle size)
            if seq % 50 == 0:
                df = pd.DataFrame(data)
                df.to_csv("kline_data.csv", index=False)
                print(f"Saved {len(data)} rows (last close {k['c']} at {now})")

asyncio.run(collect_kline())























































