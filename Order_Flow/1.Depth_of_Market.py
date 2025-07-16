import pandas as pd
import numpy as np

# Core Trade Data:
# Date, Time, Sequence, DepthSequence
# Price, Volume, TradeType
# AskPrice, BidPrice, AskSize, BidSize
# TotalAskDepth, TotalBidDepth

# Order Book Levels (DOM):
# AskDOM_0 to AskDOM_19: Volumes or prices at ask levels 0 to 19.
# BidDOM_0 to BidDOM_19: Volumes or prices at bid levels 0 to 19.

# AskDOMPrice, BidDOMPrice: Possibly best ask and bid price levels.

# Session Stats:
# Datetime, SessionType
# ValueArea, MovingPOC (Point of Control)

# Cumulative Delta (CD) Stats:
# CD_Ask, CD_Bid, CD_Total

# VWAP Bands:
# vwap, vwap_sd1_top, vwap_sd1_bottom, ..., vwap_sd4_bottom
# Other:



# Peaks_Valleys_VA, Index
##### This function tell you first level biggest volume
def identify_big_position(data: pd.DataFrame)->pd.DataFrame:

    dom_cols = [x for x in data.columns if "DOM_" in x]
    if len(dom_cols) == 0:
        raise Exception("Dataframe passed has no DOM col.")
    else:
        dom_cols_ask = [x for x in data.columns if "AskDOM_" in x] + ["AskSize"]
        dom_cols_bid = [x for x in data.columns if "BidDOM_" in x] + ["BidSize"]

        data['Ask_Max'] = np.array()(data[dom_cols_ask].idxmax(axis=1))
        data['Bid_Max'] = np.array()(data[dom_cols_bid].idxmax(axis=1))
    return data

###### Remove DOM columns for better performance
def remove_DOM_columns(data: pd.DataFrame)->pd.DataFrame:
    dom_cols = [x for x in data.columns if "DOM_" in x]
    return data.drop(dom_cols, axis=1)


###### Sum of first N level(i am consider only 5 level)
def sum_first_n_DOM_levels(data: pd.DataFrame, l1_side_to_sum: str = "ask", l1_level_to_sum: int = 5)->pd.DataFrame:
    l1_side_to_sum = str(l1_side_to_sum).upper()
    dom_side = "AskDOM_" if l1_side_to_sum == "ASK" else "BidDOM_"
    dom_cols = [x for x in data.columns if dom_side in x]

    if l1_level_to_sum > len(dom_cols):
        raise Exception("Data provided less DOM levels")
    else:
        dom_cols = dom_cols[:l1_level_to_sum]


    if l1_level_to_sum == "ASK":
        data["DOMSumAsk_" + str(l1_level_to_sum)] = data[dom_cols].sum(axis=1)
    elif l1_level_to_sum == "BID":
        data["DOMSumBid_" + str(l1_level_to_sum)] = data[dom_cols].sum(axis=1)
    else:
        raise Exception("No correct DOM side")
    

    return data

# Think of the DOM shape as describing:
# Is the liquidity evenly spread across multiple levels?
# Or is most of the liquidity concentrated at just one or two levels?

# If liquidity is spread evenly, Shape approaches 1.
# If liquidity is concentrated, Shape drops towards 0.

# Shape = Liquidity spread measure.
# Higher shape → Even spread.
# Lower shape → Concentrated liquidity.

# Formula:-
# Shape = (Sum of volumes in top N levels) / (Max volume in top N levels × N)


def get_DOM_shape(data: pd.DataFrame, l1_level_to_watch: int=5)->pd.DataFrame:
    ask_dom_columns = [x for x in data.columns if "AskDOM_" in x]
    bid_dom_columns = [x for x in data.columns if "BidDOM_" in x]

    if l1_level_to_watch > len(ask_dom_columns) or l1_level_to_watch > len(bid_dom_columns):
        raise Exception("Data provided has less DOM levels")
    else:
        ask_dom_columns = ask_dom_columns[:l1_level_to_watch]
        bid_dom_columns = bid_dom_columns[:l1_level_to_watch]

    data["DOMSumAsk_" + str(l1_level_to_watch) + "_Shape"] = (data[ask_dom_columns].sum(axis=1)) / (np.max(data[ask_dom_columns], axis=1) * l1_level_to_watch)
    data["DOMSumBid_" + str(l1_level_to_watch) + "_Shape"] = (data[bid_dom_columns].sum(axis=1)) / (np.max(data[bid_dom_columns], axis=1) * l1_level_to_watch)

    return data





