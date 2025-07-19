import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import animation
from data import CSVStockData

############## A binomial random variable and return log-likelihood ###################
def log_likelihood(time_series):
    p = np.mean(time_series)
    heads = sum(time_series)
    tails = len(time_series) - heads

    return heads * np.log(p + 1e-20) + tails * np.log(1-p + 1e-20)



############### Detect Regime change #############################
def detect_regime_change(time_series, time_series_labels = None, stride=6, k=0.05):
    '''This function detects the point in time where a change in the underlying probability regime
       is likely.'''


    mdl = []
    regime_change_indicators = []
    regime_change_time = None

    for n in range(1, len(time_series)):
        neg_log_likelihood = -log_likelihood(time_series[:n]) - log_likelihood(time_series[n:])
        penalty = 0.5 * (np.log(n) + np.log(len(time_series)-n))

        if n==1:
            mdl.append((neg_log_likelihood + penalty))
        else:
            mdl.append(mdl[-1]*(1-k) + (neg_log_likelihood + penalty)*k)

        detection_window = mdl[-(2*stride):]
        min_ = detection_window.index(min(detection_window))
        if n>20 and regime_change_time is None:
            if min_ > 0 and min_ < 2*stride:
                if np.mean(detection_window[:min_]) < np.mean(detection_window[min_:]):
                    if time_series_labels is not None:
                        regime_change_time = pd.to_datetime(time_series_labels[n])
                    else:
                        regime_change_time = n

    
    if time_series_labels is None:
        return pd.Series(mdl, index=np.arange(1, len(time_series))), regime_change_time
    
    return pd.Series(mdl, index=time_series_labels[1:]), regime_change_time
    



class RegimeChangeAnimator(object):
    def __init__(self, mdl, regime_change_date, closing_prices=None):
        """
        Initializes a subplot figure with two panes and 4 artist:
         - One to plot the MDL over time
         - One to plot the closing price of the underlying stock over time
         - One to add a vertical line where the regime change was detected
         - One to add an annotation to where the regime change was detected
         
        Args:
            mdl (pd.Series): Series of minimum description lengths
            regime_change_date (datetime.date): The date of the detected regime change
            closing_prices (pd.Series): A series of closing prices 
            if the regime change detection was run on actual stock data
        
        Returns:
            None
        """
        
        self.mdl = mdl
        self.closing_prices = closing_prices
        self.regime_change_date = regime_change_date
        
        if closing_prices is not None:
            self.f, self.a = plt.subplots(2, 1, figsize=(6,7))
            self.mdl_line, = self.a[0].plot([], [], c='red')
            self.closing_price_line, = self.a[1].plot([], [])
            self.regime_change_line, = self.a[1].plot([], [], c='green')
            self.regime_change_annotation = self.a[1].text(0, 0, '', 
                                                           backgroundcolor='white', 
                                                           c='green',
                                                           fontweight='bold',
                                                           fontstyle='italic', 
                                                           transform=self.a[1].transAxes)
            
        else:
            self.f, self.a = plt.subplots(1, 1, figsize=(6,7))
            self.mdl_line, = self.a.plot([], [], c='red')
            self.regime_change_line, = self.a.plot([], [], c='green')
            self.regime_change_annotation = self.a.text(0, 0, '',
                                                        backgroundcolor='white', 
                                                        c='green',
                                                        fontweight='bold',
                                                        fontstyle='italic', 
                                                        transform=self.a.transAxes)
    
    def init(self):
        """
        Sets the correct axis limits and -labels for the two subplots and 
        returns all four artists, which is required for the animation to work
        
        Returns:
            mdl_line (matplotlib.lines.Line2D): Artist to draw MDL over time
            regime_change_line (matplotlib.lines.Line2D): Artist to draw a vertical line
            regime_change_annotation (matplotlib.text): Artist to annotate the regime change date
            closing_price_line (matplotlib.lines.Line2D): Artist to draw closing prices over time 
            (only if closing prices were provided when creating the instance)
        """
        
        self.mdl_line.set_data([], [])
        
        if self.closing_prices is not None:
            self.closing_price_line.set_data([], [])
            
            # upper pande: mdl
            self.a[0].set_xlim((min(self.mdl.index), max(self.mdl.index)))
            self.a[0].set_ylim((min(self.mdl) - 1, max(self.mdl) + 1))
            self.a[0].tick_params(axis='x', labelrotation=20)
            self.a[0].set_ylabel("MDL (Exp. MA)")
            
            # lower pane: closing prices
            self.a[1].set_xlim((min(self.mdl.index), max(self.mdl.index)))
            self.a[1].set_ylim((min(self.closing_prices) - 1, max(self.closing_prices) + 1))
            self.a[1].tick_params(axis='x', labelrotation=20)
            self.a[1].set_ylabel("$ Close")
            
            return (self.mdl_line, 
                    self.regime_change_line, 
                    self.regime_change_annotation, 
                    self.closing_price_line,)
        
        self.a.set_xlim((min(self.mdl.index), max(self.mdl.index)))
        self.a.set_ylim((min(self.mdl) - 1, max(self.mdl) + 1))
        self.a.tick_params(axis='x', labelrotation=20)
        self.a.set_ylabel("MDL (Exp. MA)")
        
        return (self.mdl_line, 
                self.regime_change_line, 
                self.regime_change_annotation,)
        

    def animator(self, data):
        """
        Updates all four artists in the plot:
         - MDL and closing prices are updated every single time
         - Regime change + annotation are only updated once where the regime change was detected
         
        Args:
            data (Tuple): A tuple holding the data (mdl, regime_change_date, closing_prices) 
            to be updated in the chart(s)
        
        Returns:
            mdl_line (matplotlib.lines.Line2D): Artist to draw MDL over time
            regime_change_line (matplotlib.lines.Line2D): Artist to draw a vertical line
            regime_change_annotation (matplotlib.text): Artist to annotate the regime change date
            closing_price_line (matplotlib.lines.Line2D): Artist to draw closing prices over time 
            (only if closing prices were provided when creating the instance)
        """
        
        mdl, regime_change_date, closing_prices = data
        
        if regime_change_date == mdl.index[-1]:
            y_bounds = [min(self.mdl) - 1, max(self.mdl) + 1] if self.closing_prices is None \
                else [min(self.closing_prices) - 1, max(self.closing_prices) + 1]
            
            self.regime_change_line.set_data([max(mdl.index), max(mdl.index)], y_bounds)
            self.regime_change_annotation.set_x(list(mdl.index).index(regime_change_date)/len(self.mdl.index))
            self.regime_change_annotation.set_y(0.2)
            self.regime_change_annotation.set_text(str(regime_change_date) if type(regime_change_date) == int 
                                                   else regime_change_date.strftime('%Y-%m-%d'))
            
        if self.closing_prices is not None:
            self.mdl_line.set_data(mdl.index, mdl)
            self.closing_price_line.set_data(pd.to_datetime(closing_prices.index), closing_prices)
            
            return (self.mdl_line, 
                    self.regime_change_line, 
                    self.regime_change_annotation, 
                    self.closing_price_line,)
        
        self.mdl_line.set_data(mdl.index, mdl)
        
        return (self.mdl_line, 
                self.regime_change_line, 
                self.regime_change_annotation,)
    
    def animate(self):
        """
        Just a wrapper function for matplotlibs FuncAnimation API
        
        Returns:
            Instance of matplotlib.animation.FuncAnimation
        """
        
        return animation.FuncAnimation(self.f, 
                                       self.animator, 
                                       init_func=self.init,
                                       frames=[(self.mdl[:i], self.regime_change_date, 
                                                [] if self.closing_prices is None else self.closing_prices[:i]) 
                                               for i in range(1, len(self.mdl) + 1)], 
                                       interval=20, 
                                       blit=True, 
                                       repeat=False)
    






