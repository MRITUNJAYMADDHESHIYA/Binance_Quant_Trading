import pandas as pd
import numpy as np

def directional_change_regime_profile(data, threshold):
    prices = data['Price'].values
    times = data.index.values

    last_extreme = prices[0]
    direction = None
    dc_events = []

    last_event_time = times[0]

    for idx, (price, time) in enumerate(zip(prices, times)):
        tmv = (price - last_extreme) / last_extreme
        log_return = np.log(price / last_extreme)

        if isinstance(time, np.datetime64):
            time_delta = (time - last_event_time) / np.timedelta64(1, 's')
        else:
            time_delta = time - last_event_time

        if time_delta == 0:
            time_adjusted_return = np.nan
        else:
            time_adjusted_return = (tmv / time_delta) * threshold

        if direction != 'up' and log_return >= threshold:
            direction = 'up'
            dc_events.append({
                'Index': idx,
                'Time': time,
                'Price': price,
                'Direction': 'up',
                'LogReturn': log_return,
                'TMV': tmv,
                'Time_Delta': time_delta,
                'Time_Adjusted_Return': time_adjusted_return
            })
            last_extreme = price
            last_event_time = time

        elif direction != 'down' and log_return <= -threshold:
            direction = 'down'
            dc_events.append({
                'Index': idx,
                'Time': time,
                'Price': price,
                'Direction': 'down',
                'LogReturn': log_return,
                'TMV': tmv,
                'Time_Delta': time_delta,
                'Time_Adjusted_Return': time_adjusted_return
            })
            last_extreme = price
            last_event_time = time

    dc_df = pd.DataFrame(dc_events)

    # --- DC-Based Regime Profiling ---
    if dc_df.empty:
        return None, None

    num_dc_events = len(dc_df)
    avg_magnitude_dc = dc_df['LogReturn'].abs().mean()
    avg_tmv = dc_df['TMV'].abs().mean()
    avg_time_delta = dc_df['Time_Delta'].mean()
    std_time_delta = dc_df['Time_Delta'].std()
    avg_time_adjusted_return = dc_df['Time_Adjusted_Return'].abs().mean()

    regime_profile = {
        'Number_of_DC_Events': num_dc_events,
        'Average_DC_Magnitude': avg_magnitude_dc,
        'Average_TMV': avg_tmv,
        'Average_DC_Duration': avg_time_delta,
        'Std_DC_Duration': std_time_delta,
        'Average_Time_Adjusted_Return': avg_time_adjusted_return
    }

    return dc_df, regime_profile
