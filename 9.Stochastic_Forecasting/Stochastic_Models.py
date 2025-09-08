import requests
import time
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from tqdm import tqdm

######################## Data 1H BTC ########################1
def fetch_binance_klines(symbol='BTCUSDT', interval='1h', limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    cols = ["open_time","open","high","low","close","volume","close_time",
            "quote_asset_volume","num_trades","taker_buy_base","taker_buy_quote","ignore"]
    df = pd.DataFrame(data, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit='ms')
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df[["open_time","open","high","low","close","volume"]].copy()
    df.set_index("open_time", inplace=True)
    return df

############################ log price and log returns ############################
def prepare_series(df):
    df = df.copy().dropna()
    df["log_close"] = np.log(df["close"])
    df["ret"] = df["log_close"].diff()
    df = df.dropna()
    return df

# -------------------------
# Fit GBM parameters (mu, sigma) on log-returns
# GBM model for log price: d log S = (mu - 0.5 sigma^2) dt + sigma dW
# For discrete hourly returns r_t ~ Normal((mu-0.5*sigma^2)*dt, sigma^2 * dt)
# dt = 1 (hour) in units we use; we'll estimate annualized if needed.
# -------------------------
def fit_gbm(df, dt=1.0):
    r = df["ret"].values
    # sample mean and variance of returns
    m = np.mean(r) / dt
    s2 = np.var(r, ddof=1) / dt
    sigma = np.sqrt(s2)
    # recover mu from mean = mu - 0.5*sigma^2  => mu = mean + 0.5*sigma^2
    mu = m + 0.5 * sigma**2
    return {"mu": float(mu), "sigma": float(sigma)}

# -------------------------
# Simulate GBM Monte Carlo
# -------------------------
def simulate_gbm(logS0, mu, sigma, horizon, n_paths=1000, dt=1.0, seed=None):
    rng = np.random.default_rng(seed)
    steps = horizon
    # increments: shape (steps, n_paths)
    dW = rng.normal(loc=(mu - 0.5*sigma**2)*dt, scale=sigma*np.sqrt(dt), size=(steps, n_paths))
    # construct log price paths
    log_paths = np.empty((steps+1, n_paths))
    log_paths[0] = logS0
    for t in range(1, steps+1):
        log_paths[t] = log_paths[t-1] + dW[t-1]
    return log_paths  # rows: t=0..horizon

# -------------------------
# Fit Ornstein-Uhlenbeck (OU) process to log-price: dX = theta*(mu - X) dt + sigma dW
# We'll fit by MLE using Euler discretization (Gaussian)
# Discrete: X_{t+1} = X_t + theta*(mu - X_t)*dt + sigma * sqrt(dt) * eps
# eps ~ N(0,1)
# -------------------------
def fit_ou(X, dt=1.0):
    X = np.asarray(X)
    X_t = X[:-1]
    X_tp1 = X[1:]
    n = len(X_t)
    # We'll use linear regression to get initial guesses: X_tp1 - X_t = a + b * X_t + noise
    Y = X_tp1 - X_t
    A = np.column_stack([np.ones_like(X_t), -X_t])
    beta, *_ = np.linalg.lstsq(A, Y, rcond=None)
    a_init, b_init = beta  # Y ≈ a - b X_t
    theta_init = b_init / dt
    mu_init = a_init / (theta_init*dt) if theta_init != 0 else np.mean(X)
    resid = Y - (a_init - b_init*X_t)
    sigma_init = np.std(resid)/np.sqrt(dt)
    # MLE objective (negative log-likelihood)
    def neglog(params):
        theta, mu, sigma = params
        if sigma <= 0:
            return 1e12
        pred_mean = X_t + theta*(mu - X_t)*dt
        var = sigma**2 * dt
        ll = -0.5 * np.sum((X_tp1 - pred_mean)**2 / var + np.log(2*np.pi*var))
        return -ll
    x0 = np.array([max(1e-6,theta_init), mu_init, max(1e-6,sigma_init)])
    bounds = [(1e-8, None), (None, None), (1e-8, None)]
    res = minimize(neglog, x0, bounds=bounds)
    theta_mle, mu_mle, sigma_mle = res.x
    return {"theta": float(theta_mle), "mu": float(mu_mle), "sigma": float(sigma_mle), "success": res.success}


# Simulate OU Monte Carlo
# Euler discretization for X_{t+1}
def simulate_ou(X0, theta, mu, sigma, horizon, n_paths=1000, dt=1.0, seed=None):
    rng = np.random.default_rng(seed)
    steps = horizon
    paths = np.empty((steps+1, n_paths))
    paths[0] = X0
    for t in range(1, steps+1):
        eps = rng.normal(size=n_paths)
        paths[t] = paths[t-1] + theta*(mu - paths[t-1])*dt + sigma*np.sqrt(dt)*eps
    return paths


# Utility to compute percentiles and plot
def plot_forecasts(dates_index, observed_log, sim_log_paths, title="Forecast", ylabel="log-price"):
    # sim_log_paths shape (steps+1, n_paths)
    import matplotlib.dates as mdates
    steps_plus1, npaths = sim_log_paths.shape
    t = np.arange(steps_plus1)
    median = np.median(sim_log_paths, axis=1)
    p05 = np.percentile(sim_log_paths, 5, axis=1)
    p95 = np.percentile(sim_log_paths, 95, axis=1)

    # convert to price scale
    median_p = np.exp(median)
    p05_p = np.exp(p05)
    p95_p = np.exp(p95)
    obs_p = np.exp(observed_log)

    # plot
    plt.figure(figsize=(12,6))
    # observed historical
    hist_len = len(observed_log)
    plt.plot(dates_index[-hist_len:], obs_p, label="Observed (hist)", linewidth=1.5)
    # forecast index
    last_time = dates_index[-1]
    freq = dates_index.freq if getattr(dates_index, 'freq', None) is not None else (dates_index[-1]-dates_index[-2])
    # create index for forecast horizon
    future_index = pd.date_range(start=last_time + freq, periods=steps_plus1-1, freq=freq)
    # Plot median and CI
    plt.plot(np.concatenate([[last_time], future_index]), np.concatenate([[np.exp(observed_log[-1])], median_p[1:]]),
             label="Median forecast", linewidth=2)
    plt.fill_between(np.concatenate([[last_time], future_index]),
                     np.concatenate([[np.exp(observed_log[-1])], p05_p[1:]]),
                     np.concatenate([[np.exp(observed_log[-1])], p95_p[1:]]),
                     alpha=0.25, label="90% CI")
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Price (USDT)")
    plt.legend()
    plt.grid(True)
    plt.show()


#######################################End-to-end: fetch -> fit -> forecast -> plot#############################
def run_pipeline(symbol='BTCUSDT', interval='1h', limit=1000, horizon=24, n_paths=500, seed=42):
    print("Fetching data...")
    df = fetch_binance_klines(symbol=symbol, interval=interval, limit=limit)
    print(f"Downloaded {len(df)} rows, from {df.index[0]} to {df.index[-1]}")
    df = prepare_series(df)
    # Fit GBM on log-returns
    gbm_params = fit_gbm(df, dt=1.0)
    # Fit OU on log-price
    ou_params = fit_ou(df["log_close"].values, dt=1.0)

    print("\nFitted parameters:")
    print("GBM:", gbm_params)
    print("OU:", ou_params)

    logS0 = df["log_close"].values[-1]
    print(f"\nLatest price: {np.exp(logS0):.2f} USDT  at {df.index[-1]}")

    # Simulate GBM and OU
    print("\nSimulating Monte Carlo paths...")
    sim_gbm = simulate_gbm(logS0, gbm_params["mu"], gbm_params["sigma"], horizon=horizon, n_paths=n_paths, dt=1.0, seed=seed)
    sim_ou = simulate_ou(logS0, ou_params["theta"], ou_params["mu"], ou_params["sigma"], horizon=horizon, n_paths=n_paths, dt=1.0, seed=seed+1)

    # Plot GBM forecast
    plot_forecasts(df.index, df["log_close"].values, sim_gbm, title=f"GBM Forecast for {symbol} ({interval})")
    # Plot OU forecast
    plot_forecasts(df.index, df["log_close"].values, sim_ou, title=f"OU Forecast for {symbol} ({interval})")

    # Simple summary: median and 5/95 percentiles at horizon
    gbm_end = sim_gbm[-1]
    ou_end = sim_ou[-1]
    summary = {
        "GBM_median": float(np.median(gbm_end)),
        "GBM_5%": float(np.percentile(gbm_end,5)),
        "GBM_95%": float(np.percentile(gbm_end,95)),
        "OU_median": float(np.median(ou_end)),
        "OU_5%": float(np.percentile(ou_end,5)),
        "OU_95%": float(np.percentile(ou_end,95)),
    }
    # convert to price
    for k in list(summary.keys()):
        summary[k.replace("_median","_price").replace("_5%","_5p").replace("_95%","_95p")] = float(np.exp(summary[k]))
        del summary[k]
    print("\nForecast summaries (horizon = next {} hours):".format(horizon))
    for k,v in summary.items():
        print(f"  {k}: {v:.2f}")
    return df, gbm_params, ou_params, sim_gbm, sim_ou



if __name__ == "__main__":
    df, gbm_params, ou_params, sim_gbm, sim_ou = run_pipeline(limit=1000, horizon=24, n_paths=200)
