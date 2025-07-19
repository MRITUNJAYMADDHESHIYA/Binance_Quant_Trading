import os
import pandas as pd
import numpy as np
import json
import urllib

def coin_generator(probabilities, breakpoint, k):
    '''k            ->length of the generated series
       breakpoint   -> index at which probability regime changes from p1 to p2
       probabilities-> p1 and p2'''  
    
    if(breakpoint <= 0 or breakpoint >= k):
        raise Exception("brakpoint must be  1 to k-1")
    for i in range(k):
        yield (np.random.random() <= probabilities[i >= breakpoint])*1


# ############### Example
# probabilities = [0.1, 0.8]  # Before breakpoint: 10% chance of 1, after breakpoint: 80% chance of 1
# breakpoint = 50             # Regime change at index 50
# k = 100                     # Total length of sequence
# sequence = list(coin_generator(probabilities, breakpoint, k))
# print(sequence)


class CSVStockData:
    """
    Load tick-level or aggregated trade data from CSV.
    Assumes CSV has 'Time' and 'Price' columns.
    """
    def __init__(self, filepath):
        self.stock_data = pd.read_csv(filepath)
        
        # Preprocess 'Time' column to handle problematic timezone format
        self.stock_data['Time'] = self.stock_data['Time'].str.replace(' +0530 IST', '+05:30', regex=False)
        self.stock_data['Time'] = pd.to_datetime(self.stock_data['Time']) #nanosecond precision
        self.stock_data = self.stock_data.sort_values('Time') #sort the time
    
    
    def closing_prices(self, start_date, end_date, real=False):
        # Parse start and end times
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        # Subset data between start_date and end_date
        data_subset = self.stock_data.loc[
            (self.stock_data['Time'] >= start_date) &
            (self.stock_data['Time'] <= end_date)
        ].copy()
        
        dates = data_subset['Time'].tolist()
        
        if real:
            # Return actual prices (used instead of 'Close')
            return data_subset['Price'].astype(float).tolist(), dates
        
        # Binary up/down sequence (tick movement)
        prices = data_subset['Price'].tolist()
        binary_sequence = [int(prices[i] > prices[i-1]) for i in range(1, len(prices))]
        return binary_sequence, dates[1:]




# # Load CSV:
# csv_data = CSVStockData('C:/Users/Mritunjay Maddhesiya/OneDrive/Desktop/Binance/Order_Flow/Data/aggTrade1.csv')
# # Define start and end times (ensure timezone and nanoseconds included properly):
# start_date = '2025-03-14 00:00:02.764823793+05:30'
# end_date = '2025-03-14 23:59:59.952502896+05:30'
# # Get actual prices:
# prices, dates = csv_data.closing_prices(start_date, end_date, real=True)
# # Get binary sequence:
# binary_sequence, dates = csv_data.closing_prices(start_date, end_date, real=False)
# print(binary_sequence)




