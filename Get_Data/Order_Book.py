# import asyncio
# import websockets
# import pandas as pd
# import json
# import time

# async def test():
#     url = "wss://stream.binance.com:9443/ws/btcusdt@depth5@100ms"
#     async with websockets.connect(url) as ws:
#         while True:
#             msg = await ws.recv()
#             data = json.loads(msg)   # Convert JSON string → Python dict

#             bids = pd.DataFrame(data["bids"], columns=["price", "volume"])
#             asks = pd.DataFrame(data["asks"], columns=["price", "volume"])

#             print("\nBIDS (top 5):")
#             print(bids)

#             print("\nASKS (top 5):")
#             print(asks)

#             # time.stop(1)  # Pause for 1 second before the next iteration

# asyncio.run(test())


import asyncio
import websockets
import json
import pandas as pd
import time

async def orderbook_snapshot(symbol="btcusdt"):
    url = f"wss://stream.binance.com:9443/ws/{symbol}@depth20@100ms"
    last_snapshot_time = time.time()

    async with websockets.connect(url) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)

            # Convert order book data to DataFrames
            bids = pd.DataFrame(data["bids"], columns=["price", "qty"], dtype=float)
            asks = pd.DataFrame(data["asks"], columns=["price", "qty"], dtype=float)

            now = time.time()
            if now - last_snapshot_time >= 1.0:  # Take snapshot every 1 sec
                print(f"\n===== Snapshot @ {pd.Timestamp.utcnow()} =====")

                print("\nBIDS (Top 10):")
                print(bids.head(10).to_string(index=False))

                print("\nASKS (Top 10):")
                print(asks.head(10).to_string(index=False))

                last_snapshot_time = now

asyncio.run(orderbook_snapshot("btcusdt"))
