"""
indicators.py

純テクニカル指標の計算専用モジュール。

- MA / BB / RSI / 傾き といった「数値そのもの」を計算
- Tまわりの解釈（押し目判定 / Tスコア / モード判定など）は
  t_logic.compute_t_metrics に委譲
- Q / V スコアはここで算出して、最終的な tech dict を組み立てる

UI 側（ヘッダー / Qタブ / Tタブ / QVTタブ）は、このモジュールが返す
dict（tech）だけを見ればよい。
"""

from typing import Optional, Dict, Any

import pandas as pd

from modules.t_logic import compute_t_metrics


# -----------------------------------------------------------
# 単純テクニカル計算
# -----------------------------------------------------------


def calc_moving_averages(df: pd.DataFrame, close_col: str) -> pd.DataFrame:
    """25 / 50 / 75 日移動平均を追加する。"""
    df["25MA"] = df[close_col].rolling(25).mean()
    df["50MA"] = df[close_col].rolling(50).mean()
    df["75MA"] = df[close_col].rolling(75).mean()
    return df


def calc_bollinger_bands(df: pd.DataFrame, close_col: str) -> pd.DataFrame:
    """
    ボリンジャーバンド（20MA ± 1σ, 2σ）を追加する。

    - BB_+1σ, BB_+2σ, BB_-1σ, BB_-2σ
    """
    df["20MA"] = df[close_col].rolling(20).mean()
    df["20STD"] = df[close_col].rolling(20).std()

    df["BB_+1σ"] = df["20MA"] + df["20STD"]
    df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
    df["BB_-1σ"] = df["20MA"] - df["20STD"]
    df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]
    return df


def calc_rsi(df: pd.DataFrame, close_col: str, period: int = 14) -> pd.DataFrame:
    """標準的な RSI を計算して 'RSI' 列に追加。"""
    delta = df[close_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, 1e-10)

    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def calc_slope(series: pd.Series, window: int = 4) -> float:
    """
    直近 window 本での傾き（%）をざっくり計算。
    - 正: 上向き
    - 負: 下向き
    """
    s = series.dropna()
    if len(s) < window + 1:
        return 0.0
    start = float(s.iloc[-window - 1])
    end = float(s.iloc[-1])
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def slope_arrow(series: pd.Series) -> str:
    """直近2本の変化方向から矢印アイコンを返す。"""
    s = series.dropna()
    if len(s) < 2:
        return "→"
    diff = float(s.iloc[-1]) - float(s.iloc[-2])
    if diff > 0:
        return "↗"
    elif diff < 0:
        return "↘"
    return "→"


# -----------------------------------------------------------
# Q / V スコア用の簡易ユーティリティ
# -----------------------------------------------------------


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _score_quality(
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
) -> float:
    """
    ビジネスの質(Q)の簡易スコアリング。
    - ROE / ROA / 自己資本比率を 0〜100 にざっくり正規化して平均。
    """

    scores = []

    if roe is not None:
        # 0〜25% を 0〜100 にマップ（25%以上は頭打ち）
        scores.append(_clamp(roe / 25.0 * 100.0, 0.0, 100.0))

    if roa is not None:
        # 0〜15% を 0〜100 にマップ
        scores.append(_clamp(roa / 15.0 * 100.0, 0.0, 100.0))

    if equity_ratio is not None:
        # 0〜60% を 0〜100 にマップ（60%以上は頭打ち）
        scores.append(_clamp(equity_ratio / 60.0 * 100.0, 0.0, 100.0))

    if not scores:
        return 50.0  # 情報がなければ中立

    return round(sum(scores) / len(scores), 1)


def _score_valuation(
    per: Optional[float],
    pbr: Optional[float],
    dividend_yield: Optional[float],
) -> float:
    """
    バリュエーション(V)の簡易スコアリング。
    - PER / PBR は低いほど高評価
    - 配当利回りは高いほど高評価
    """

    scores = []

    if per is not None and per > 0:
        # PER 10〜30 をざっくり 100〜0 にマップ
        per_score = 100.0 - _clamp((per - 10.0) / 20.0 * 100.0, 0.0, 100.0)
        scores.append(per_score)

    if pbr is not None and pbr > 0:
        # PBR 1〜5 をざっくり 100〜0 にマップ
        pbr_score = 100.0 - _clamp((pbr - 1.0) / 4.0 * 100.0, 0.0, 100.0)
        scores.append(pbr_score)

    if dividend_yield is not None and dividend_yield > 0:
        # 利回り 0〜5% を 0〜100 にマップ（5%以上は頭打ち）
        dy_score = _clamp(dividend_yield / 5.0 * 100.0, 0.0, 100.0)
        scores.append(dy_score)

    if not scores:
        return 50.0

    return round(sum(scores) / len(scores), 1)


# -----------------------------------------------------------
# メイン：compute_indicators
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
) -> Dict[str, Any]:
    """
    テクニカル指標 + Q/V/T スコアをまとめて計算し、UI 用の dict を返す。

    - MA / BB / RSI / slope / arrow などの「数値」はこのモジュールで計算
    - T 周り（押し目判定 / Tスコア / モード / コメント）は t_logic に委譲
    - Q / V スコアはここで算出
    """

    # --- テクニカル計算 ---
    df = calc_moving_averages(df, close_col)
    df = calc_bollinger_bands(df, close_col)
    df = calc_rsi(df, close_col)

    # 有効データ（テクニカルがすべて埋まっている行）
    df_valid = df.dropna(
        subset=[
            close_col,
            "25MA",
            "50MA",
            "75MA",
            "BB_+1σ",
            "BB_+2σ",
            "BB_-1σ",
            "BB_-2σ",
            "RSI",
        ]
    )
    if df_valid.empty or len(df_valid) < 5:
        raise ValueError("テクニカル指標を計算するためのデータが不足しています。")

    last = df_valid.iloc[-1]

    # --- 基本値 ---
    price = float(last[close_col])
    ma_25 = float(last["25MA"])
    ma_50 = float(last["50MA"])
    ma_75 = float(last["75MA"])
    rsi = float(last["RSI"])

    bb_plus1 = float(last["BB_+1σ"])
    bb_plus2 = float(last["BB_+2σ"])
    bb_minus1 = float(last["BB_-1σ"])
    bb_minus2 = float(last["BB_-2σ"])

    # --- 傾き & 矢印 ---
    slope_25 = calc_slope(df["25MA"])
    slope_50 = calc_slope(df["50MA"])
    slope_75 = calc_slope(df["75MA"])

    arrow_25 = slope_arrow(df["25MA"])
    arrow_50 = slope_arrow(df["50MA"])
    arrow_75 = slope_arrow(df["75MA"])

    # --- PER / PBR / 予想PER ---
    per: Optional[float] = None
    pbr: Optional[float] = None

    if eps not in (None, 0):
        per = price / eps
    if bps not in (None, 0):
        pbr = price / bps

    per_fwd_calc: Optional[float] = None
    if per_fwd not in (None, 0):
        per_fwd_calc = per_fwd
    elif eps_fwd not in (None, 0):
        per_fwd_calc = price / eps_fwd

    # --- Tロジックをまとめて計算（t_logic） ---
    t_metrics = compute_t_metrics(
        price=price,
        ma_25=ma_25,
        ma_50=ma_50,
        ma_75=ma_75,
        rsi=rsi,
        bb_plus1=bb_plus1,
        bb_plus2=bb_plus2,
        bb_minus1=bb_minus1,
        bb_minus2=bb_minus2,
        slope_25=slope_25,
        low_52w=low_52w,
        high_52w=high_52w,
        per=per,
        pbr=pbr,
    )

    t_score = float(t_metrics["t_score"])

    # --- Q / V / QVT スコア ---
    q_score = _score_quality(roe, roa, equity_ratio)
    v_score = _score_valuation(per, pbr, dividend_yield)
    qvt_score = round((q_score + v_score + t_score) / 3.0, 1)

    # --- 返却 dict ---
    result: Dict[str, Any] = {
        # 生データ
        "df": df,
        "df_valid": df_valid,

        # 価格
        "close": price,

        # MA (新しい名前に統一)
        "ma_25": ma_25,
        "ma_50": ma_50,
        "ma_75": ma_75,

        # MA slope
        "slope_25": slope_25,
        "slope_50": slope_50,
        "slope_75": slope_75,

        # slope arrows
        "arrow_25": arrow_25,
        "arrow_50": arrow_50,
        "arrow_75": arrow_75,

        # BB
        "bb_plus1": bb_plus1,
        "bb_plus2": bb_plus2,
        "bb_minus1": bb_minus1,
        "bb_minus2": bb_minus2,

        # RSI
        "rsi": rsi,

        # 52W
        "high_52w": high_52w,
        "low_52w": low_52w,

        # ファンダ系
        "eps": eps,
        "bps": bps,
        "eps_fwd": eps_fwd,
        "per": per,
        "pbr": pbr,
        "per_fwd": per_fwd_calc,
        "roe": roe,
        "roa": roa,
        "equity_ratio": equity_ratio,
        "dividend_yield": dividend_yield,

        # Q / V / T / QVT
        "q_score": q_score,
        "v_score": v_score,
        "t_score": t_score,
        "qvt_score": qvt_score,
    }

    # Tロジックの結果をマージ
    result.update(t_metrics)

    return result
