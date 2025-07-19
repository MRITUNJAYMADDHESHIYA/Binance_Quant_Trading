import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from hmmlearn.hmm import GaussianHMM

class dc_calculator():
	def __init__(self):
		self.prices   = None
		self.time     = None
		self.TMV_list = []   #List to store Threshold-Metric Values (TMV), a normalized metric indicating price deviation from last extremum point.
		self.T_list   = []   #List to store "T", a counter tracking how long since the last extremum point.
		self.colors   = []   #Used for plotting (tracks color coding for price states)
		self.events   = []   #Labels to track event types like 'Upward Overshoot', 'Downward DCC', etc.
		self.regimes  = []   #store HMM regimes


	def compute_dc_variables(self, threshold: float = 0.0001):

		if self.prices is None:
			print('Please load the time series data first before proceeding with the DC parameters computation')
		else:
			self.TMV_list = []
			self.T_list = []
			self.colors = []
			self.events = []

			ext_point_n = self.prices[0]
			curr_event_max = self.prices[0]
			curr_event_min = self.prices[0]
			time_point_max = 0
			time_point_min = 0
			trend_status = 'up'
			T = 0                            #Counter for number of steps since last extremum.

			for i in range(len(self.prices)):
				TMV = (self.prices[i] - ext_point_n) / (ext_point_n * threshold)
				self.TMV_list.append(TMV)
				self.T_list.append(T)
				T += 1  #T is incremented with each iteration until a new directional change event is detected.

				if trend_status == 'up':
					self.colors.append('lime')
					self.events.append('Upward Overshoot')

					if self.prices[i] < ((1 - threshold) * curr_event_max):
						trend_status = 'down'
						curr_event_min = self.prices[i]

						ext_point_n = curr_event_max
						T = i - time_point_max

						num_points_change = i - time_point_max
						for j in range(1, num_points_change + 1):
							self.colors[-j] = 'red'
							self.events[-j] = 'Downward DCC'
					else:
						if self.prices[i] > curr_event_max:
							curr_event_max = self.prices[i]
							time_point_max = i
				else:
					self.colors.append('lightcoral')
					self.events.append('Downward Overshoot')

					if self.prices[i] > ((1 + threshold) * curr_event_min):
						trend_status = 'up'
						curr_event_max = self.prices[i]

						ext_point_n = curr_event_min			
						T = i - time_point_min

						num_points_change = i - time_point_min
						for j in range(1, num_points_change + 1):
							self.colors[-j] = 'green'
							self.events[-j] = 'Upward DCC'
					else:
						if self.prices[i] < curr_event_min:
							curr_event_min = self.prices[i]
							time_point_min = i

			self.colors = np.array(self.colors)

			print('DC variables computation has finished.')


	# Regime 0 → low volatility sideways market.
	# Regime 1 → trending market.
	# Regime 2 → high volatility choppy phase.
	def fit_hmm_and_classify(self, n_states=3):
		if not self.TMV_list:
			print("Compute DC variables before fitting HMM.")
			return
		
		# Reshape TMV for HMM (expects 2D array)
		X = np.array(self.TMV_list).reshape(-1, 1)

		# Initialize and train HMM
		model = GaussianHMM(n_components=n_states, covariance_type='full', n_iter=100)
		model.fit(X)

		# Predict hidden states (regimes)
		hidden_states = model.predict(X)

		self.regimes = hidden_states

		print(f'HMM regime classification finished. Number of regimes: {n_states}')



if __name__ == '__main__':

	df1 = pd.read_csv("C:/Users/Mritunjay Maddhesiya/OneDrive/Desktop/Binance/Order_Flow/Data/aggTrade1.csv")
	dc = dc_calculator()
	dc.prices = df1['Price'].values
	dc.time = df1['Time'].values

	dc.compute_dc_variables(threshold=0.001)  #You can adjust the threshold
	dc.fit_hmm_and_classify(n_states=3)

	# Clean 'Time' and parse
	df1['Time_cleaned'] = df1['Time'].str.replace(' IST', '', regex=False)
	time_values = pd.to_datetime(df1['Time_cleaned'], format='%Y-%m-%d %H:%M:%S.%f %z')



	regime_colors = ['purple', 'orange', 'cyan']
	plt.figure(figsize=(14, 7))
	for regime in range(3):
		mask = (dc.regimes == regime)
		plt.scatter(time_values[mask], dc.prices[mask], 
					color=regime_colors[regime], label=f'Regime {regime}', s=10)

	plt.legend(loc='upper left')
	plt.title('HMM Regime Classification')
	plt.xlabel('Time')
	plt.ylabel('Price')
	plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
	plt.gcf().autofmt_xdate()
	plt.grid(True)
	plt.tight_layout()
	plt.show()






	# Plotting
	plt.figure(figsize=(14, 7))
	scatter = plt.scatter(time_values, dc.prices, c=dc.colors, s=10)
	legend_elements = [
        Patch(facecolor='lime', label='Upward Overshoot'),
        Patch(facecolor='lightcoral', label='Downward Overshoot'),
        Patch(facecolor='green', label='Upward DCC'),
        Patch(facecolor='red', label='Downward DCC')
    ]

	plt.legend(handles=legend_elements, loc='upper left')
	plt.title('Directional Change Events with Overshoot & DCC')
	plt.xlabel('Time')
	plt.ylabel('Price')

	# Format x-axis
	plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
	plt.gcf().autofmt_xdate()

	plt.grid(True)
	plt.tight_layout()
	plt.show()
