import pandas as pd
import matplotlib.pyplot as plt

def footprint_chart_on_price(data: pd.DataFrame) -> pd.DataFrame:
    
    # Ensure Price is float, Volume is numeric
    data['Price'] = pd.to_numeric(data['Price'], errors='coerce')
    data['Volume'] = pd.to_numeric(data['Volume'], errors='coerce')

    # Classify Bid/Ask trades
    data['AskVolume'] = data.apply(lambda x: x['Volume'] if x['TradeType'] == 2 else 0, axis=1)
    data['BidVolume'] = data.apply(lambda x: x['Volume'] if x['TradeType'] == 1 else 0, axis=1)
    
    # Group by Price Level
    footprint = data.groupby('Price').agg({
        'Volume': 'sum',
        'AskVolume': 'sum',
        'BidVolume': 'sum'
    }).reset_index()

    # Calculate Delta
    footprint['Delta'] = footprint['AskVolume'] - footprint['BidVolume']

    # Sort from high to low (optional)
    footprint = footprint.sort_values('Price', ascending=False).reset_index(drop=True)

    return footprint



############# JUST FOR FUN
def plot_footprint_chart(footprint_df: pd.DataFrame):
    plt.figure(figsize=(10, 14))

    y_prices = footprint_df['Price']
    bid_volumes = footprint_df['BidVolume']
    ask_volumes = footprint_df['AskVolume']
    deltas = footprint_df['Delta']

    max_volume = max(bid_volumes.max(), ask_volumes.max())

    # Plot Bid Volumes (to the left)
    plt.barh(y_prices, -bid_volumes, color='red', label='Bid Volume')

    # Plot Ask Volumes (to the right)
    plt.barh(y_prices, ask_volumes, color='green', label='Ask Volume')

    # Plot Delta as background shading (optional)
    for idx, price in enumerate(y_prices):
        delta = deltas.iloc[idx]
        color = 'lightgreen' if delta >= 0 else 'lightcoral'
        plt.axhline(y=price, xmin=0.25, xmax=0.75, color=color, linewidth=0.5, alpha=0.3)

    plt.xlabel('Volume')
    plt.ylabel('Price')
    plt.title('Footprint Chart')
    plt.legend()
    plt.grid(True, which='both', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.show()

