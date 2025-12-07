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

# -----------------------------------------------------------
# まとめて指標を計算し dict で返す関数
# -----------------------------------------------------------

def compute_indicators(
    df: pd.DataFrame,
    close_col: str,
    high_52w: Optional[float] = None,
    low_52w: Optional[float] = None,
    eps: Optional[float] = None,
    bps: Optional[float] = None,
    eps_fwd: Optional[float] = None,
    per_fwd: Optional[float] = None,
    roe: Optional[float] = None,
    roa: Optional[float] = None,
    equity_ratio: Optional[float] = None,
    dividend_yield: Optional[float] = None,
):
    # 移動平均
    df = calc_moving_averages(df, close_col)

    # ボリンジャーバンド
    df = calc_bollinger_bands(df, close_col)

    # RSI
    df = calc_rsi(df, close_col)

    # 最新行の取り出し
    last = df.iloc[-1]

    # 傾き
    slope_25 = calc_slope(df["25MA"])
    slope_50 = calc_slope(df["50MA"])
    slope_75 = calc_slope(df["75MA"])

    # 向き（矢印）
    arrow_25 = slope_arrow(df["25MA"])
    arrow_50 = slope_arrow(df["50MA"])
    arrow_75 = slope_arrow(df["75MA"])

    # 返却用 dict
    result = {
        # 価格
        "close": last[close_col],

        # MA
        "ma_25": last["25MA"],
        "ma_50": last["50MA"],
        "ma_75": last["75MA"],

        # MA slope
        "slope_25": slope_25,
        "slope_50": slope_50,
        "slope_75": slope_75,

        # slope arrows
        "arrow_25": arrow_25,
        "arrow_50": arrow_50,
        "arrow_75": arrow_75,

        # BB
        "bb_plus1": last["BB_+1σ"],
        "bb_plus2": last["BB_+2σ"],
        "bb_minus1": last["BB_-1σ"],
        "bb_minus2": last["BB_-2σ"],

        # RSI
        "rsi": last["RSI"],

        # 52W（ファンダ）
        "high_52w": high_52w,
        "low_52w": low_52w,

        # その他ファンダ項目
        "eps": eps,
        "bps": bps,
        "eps_fwd": eps_fwd,
        "per_fwd": per_fwd,
        "roe": roe,
        "roa": roa,
        "equity_ratio": equity_ratio,
        "dividend_yield": dividend_yield,
    }

    return result
