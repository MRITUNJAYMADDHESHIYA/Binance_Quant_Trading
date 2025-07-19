import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib import animation
from statistics import variance as var
# %matplotlib inline
from IPython.display import HTML


from data import CSVStockData, coin_generator
from Detecting_Regime_using_MDL import log_likelihood, detect_regime_change, RegimeChangeAnimator

############################ 
# Load your CSV:
csv_data = CSVStockData('C:/Users/Mritunjay Maddhesiya/OneDrive/Desktop/Binance/Order_Flow/Data/aggTrade1.csv')

# Define time window (use proper formatting as explained earlier):
start_date = '2025-03-14 00:00:02.764823793+05:30'
end_date = '2025-03-14 02:20:02.731124907+05:30'


# Get binary sequence (price up/down):
binary_sequence, time_series_labels = csv_data.closing_prices(start_date, end_date, real=False)
print(binary_sequence)
print(time_series_labels)

# Run your regime change detection:
mdl_series, regime_change_time = detect_regime_change(binary_sequence, time_series_labels)

# Print detected change point:
print("Regime Change Detected At:", regime_change_time)
# Plot MDL curve:
plt.figure(figsize=(12,6))
mdl_series.plot(label='MDL')
plt.axvline(x=regime_change_time, color='red', linestyle='--', label='Regime Change Detected')
plt.xlabel('Time')
plt.ylabel('MDL Score')
plt.title('MDL Curve - Regime Change Detection')
plt.legend()
plt.grid()
plt.show()







# mdl_coin,_ = detect_regime_change(time_series=[i for i in coin_generator([0.1, 0.9], 50, 100)], k=1)
# mdl_stock,_ = detect_regime_change(*CSVStockData("^GSPC").closing_prices("2008-01-20","2009-09-30"), k=1)

# f,a = plt.subplots(1,2, figsize=(12,6))

# mdl_coin.plot(ax=a[0])
# a[0].set_ylabel('MDL')
# a[0].set_title("MDL for a simulated coin")

# mdl_stock.plot(ax=a[1])
# a[1].set_ylabel('MDL')
# a[1].set_xlabel('t')
# a[1].set_title("MDL for S&P 500")

# plt.show()