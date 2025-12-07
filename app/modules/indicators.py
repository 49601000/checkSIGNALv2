"""
純テクニカル指標の計算専用モジュール
RSI / MA / BB / 傾き など「数値だけ」を算出し、
ロジック（押し目判定・Tスコア）は t_logic.py に委譲する
"""

import pandas as pd
from typing import Optional


# -----------------------------------------------------------
# 移動平均
# -----------------------------------------------------------

def calc_moving_averages(df: pd.DataFrame, close_col: str):
    df["25MA"] = df[close_col].rolling(25).mean()
    df["50MA"] = df[close_col].rolling(50).mean()
    df["75MA"] = df[close_col].rolling(75).mean()
    return df


# -----------------------------------------------------------
# ボリンジャーバンド
# -----------------------------------------------------------

def calc_bollinger_bands(df: pd.DataFrame, close_col: str):
    df["20MA"] = df[close_col].rolling(20).mean()
    df["20STD"] = df[close_col].rolling(20).std()

    df["BB_+1σ"] = df["20MA"] + df["20STD"]
    df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
    df["BB_-1σ"] = df["20MA"] - df["20STD"]
    df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]

    return df


# -----------------------------------------------------------
# RSI
# -----------------------------------------------------------

def calc_rsi(df: pd.DataFrame, close_col: str, period: int = 14):
    delta = df[close_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, 1e-10)

    df["RSI"] = 100 - (100 / (1 + (avg_gain / avg_loss)))
    return df


# -----------------------------------------------------------
# MA の傾き
# -----------------------------------------------------------

def calc_slope(series: pd.Series, window: int = 3) -> float:
    """短期の傾きをパーセントで算出"""
    series = series.dropna()
    if len(series) < window + 1:
        return 0.0
    old = series.iloc[-window-1]
    new = series.iloc[-1]
    if old == 0:
        return 0.0
    return (new - old) / old * 100


# -----------------------------------------------------------
# MA の向きを矢印で返す
# -----------------------------------------------------------

def slope_arrow(series: pd.Series, window: int = 3) -> str:
    series = series.dropna()
    if len(series) < window + 1:
        return "→"
    diff = series.iloc[-1] - series.iloc[-window]
    if diff > 0:
        return "↗"
    elif diff < 0:
        return "↘"
    return "→"
