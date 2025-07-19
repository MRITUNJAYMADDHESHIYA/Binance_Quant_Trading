from Depth_of_Market import identify_big_position, remove_DOM_columns, sum_first_n_DOM_levels, get_DOM_shape
from Foot_Print import footprint_chart_on_price, plot_footprint_chart
from Detecting_Regime_using_Price import directional_change_regime_profile, dc_calculator

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv("C:/Users/Mritunjay Maddhesiya/OneDrive/Desktop/Binance/Order_Flow/Data/2023_06_29.csv", sep=';')
df1 = pd.read_csv("C:/Users/Mritunjay Maddhesiya/OneDrive/Desktop/Binance/Order_Flow/Data/aggTrade1.csv", sep=',')
#print(df)

# # Print initial dataframe shape and columns
# print("\n--- Raw Data Loaded ---")
# print(df.shape)
# print(df.columns.tolist())

# # Step 1: Identify Big Positions
# print("\n--- Step 1: Identify Big Positions ---")
# df = identify_big_position(df)
# print(df[['Ask_Max', 'Bid_Max']].head())

# # # Step 2: Remove DOM Columns (Optional, if you want to clean up)
# # print("\n--- Step 2: Remove DOM Columns ---")
# # df_removed_DOM = remove_DOM_columns(df)
# # print(df_removed_DOM.head())

# # Step 3: Sum of First N DOM Levels (Example: 5 levels)
# print("\n--- Step 3: Sum of First N DOM Levels ---")
# df = sum_first_n_DOM_levels(df, l1_side_to_sum="ask", l1_level_to_sum=5)
# print(df[[col for col in df.columns if "DOM_Sum_Ask" in col]].head())
# df = sum_first_n_DOM_levels(df, l1_side_to_sum="bid", l1_level_to_sum=5)
# print(df[[col for col in df.columns if "DOM_Sum_Bid" in col]].head())

# # Step 4: DOM Shape Calculation
# print("\n--- Step 4: DOM Shape ---")
# df = get_DOM_shape(df, l1_level_to_watch=5)
# print(df[[col for col in df.columns if "_Shape" in col]].head())

# step 5: foot prints
# print("\n--- Step 5: foot print ---")
# footprint_df = footprint_chart_on_price(df)
# print(footprint_df.head(100))
# plot_footprint_chart(footprint_df)

#print(df['Price'].unique())

# print(directional_change_regime_profile(df1, 0.001))


import pandas as pd
import numpy as np


# Initialize and use the DC calculator
dc = dc_calculator()

# Load prices
dc.prices = df1['Price'].values

# Optionally load time (if needed)
dc.time = df1['Time'].values

# Compute DC variables
dc.compute_dc_variables(threshold=0.001)  # You can adjust the threshold

# Plotting with legend and zoom enabled
plt.figure(figsize=(14, 7))

# Scatter plot with colors from DC
scatter = plt.scatter(range(len(dc.prices)), dc.prices, c=dc.colors, s=10)

# Create custom legend handles
from matplotlib.patches import Patch

legend_elements = [
    Patch(facecolor='lime', label='Upward Overshoot'),
    Patch(facecolor='lightcoral', label='Downward Overshoot'),
    Patch(facecolor='green', label='Upward DCC'),
    Patch(facecolor='red', label='Downward DCC')
]

plt.legend(handles=legend_elements, loc='upper left')

# Titles and labels
plt.title('Directional Change Events with Overshoot & DCC')
plt.xlabel('Index')
plt.ylabel('Price')

# Enable zoom/pan via Matplotlib's toolbar
plt.grid(True)
plt.tight_layout()
plt.show()
