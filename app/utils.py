from typing import Optional, Dict, Any
import pandas as pd

# --- モジュール呼び出し ---
from modules.indicators import (
    calc_moving_averages,
    calc_bollinger_bands,
    calc_rsi,
    calc_slope,
    slope_arrow,
)

from modules.t_logic import (
    judge_bb_signal,
    judge_signal,
    is_high_price_zone,
    is_low_price_zone,
    is_flat_ma,
    calc_timing_score,
    timing_label_from_score,
)

from modules.q_logic import score_quality
from modules.valuation import score_valuation


# ============================================================
# メイン：compute_indicators（統合ハブ）
# ============================================================

def compute_indicators(
    df: pd.DataFrame,
    close_col: str,
    high_52w: float,
    low_52w: float,
    ticker: Optional[str] = None,
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
    データ取得 → テクニカル計算 → Q/V/T → 総合QVT の統合処理。
    機能は modules/ 以下に完全分離されている。
    """

    # ---------------------------------------------------------
    # ① テクニカル指標を DataFrame に追加
    # ---------------------------------------------------------
    df = calc_moving_averages(df, close_col)
    df = calc_bollinger_bands(df, close_col)
    df = calc_rsi(df, close_col)

    df_valid = df.dropna(subset=[
        close_col,
        "25MA", "50MA", "75MA",
        "BB_+1σ", "BB_+2σ",
        "BB_-1σ", "BB_-2σ",
        "RSI"
    ])
    if df_valid.empty:
        raise ValueError("有効なテクニカルデータが不足しています。")

    # 最新値を取得
    last = df_valid.iloc[-1]
    price = float(last[close_col])

    ma25 = last["25MA"]
    ma50 = last["50MA"]
    ma75 = last["75MA"]
    rsi = last["RSI"]

    bb_upper1 = last["BB_+1σ"]
    bb_upper2 = last["BB_+2σ"]
    bb_lower1 = last["BB_-1σ"]
    bb_lower2 = last["BB_-2σ"]

    # ---------------------------------------------------------
    # ② MAの傾きを算出
    # ---------------------------------------------------------
    ma25_slope = calc_slope(df["25MA"])
    arrow25 = slope_arrow(df["25MA"])
    arrow50 = slope_arrow(df["50MA"])
    arrow75 = slope_arrow(df["75MA"])

    # ---------------------------------------------------------
    # ③ PER / PBR 計算
    # ---------------------------------------------------------
    per = price / eps if eps not in (None, 0) else None
    pbr = price / bps if bps not in (None, 0) else None

    per_fwd_calc = None
    if per_fwd not in (None, 0):
        per_fwd_calc = per_fwd
    elif eps_fwd not in (None, 0):
        per_fwd_calc = price / eps_fwd

    # ---------------------------------------------------------
    # ④ BB判定・押し目判定
    # ---------------------------------------------------------
    bb_text, bb_icon, bb_strength = judge_bb_signal(
        price, bb_upper1, bb_upper2, bb_lower1, bb_lower2
    )

    signal_text, signal_icon, signal_strength = judge_signal(
        price,
        ma25, ma50, ma75,
        bb_lower1, bb_upper1, bb_lower2,
        rsi,
        high_52w, low_52w,
    )

    # ---------------------------------------------------------
    # ⑤ 高値警戒フラグ
    # ---------------------------------------------------------
    high_price_alert = (
        price >= bb_upper1
        or (high_52w and price >= high_52w * 0.98)
        or (rsi is not None and rsi >= 70)
    )

    # ---------------------------------------------------------
    # ⑥ 順張り・逆張りスコア（視覚的判断用）
    # ---------------------------------------------------------
    highprice_score = is_high_price_zone(
        price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w
    )
    low_score = is_low_price_zone(
        price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w
    )

    is_flat = is_flat_ma(ma25, ma50, ma75)
    slope_ok = ma25_slope < 0

    # ---------------------------------------------------------
    # ⑦ モード（順張り or 逆張り）
    # ---------------------------------------------------------
    if ma25 > ma50 > ma75:
        t_mode = "trend"
    else:
        t_mode = "contrarian"

    is_downtrend = bool(ma75 > ma50 > ma25 and ma25_slope < 0)

    # ---------------------------------------------------------
    # ⑧ Q / V / T の 3 スコア
    # ---------------------------------------------------------
    q_score = score_quality(roe, roa, equity_ratio)
    v_score = score_valuation(per, pbr, dividend_yield)
    t_score = calc_timing_score(
        price, rsi,
        bb_upper1, bb_upper2,
        bb_lower1, bb_lower2,
        ma25, ma50, ma75,
        ma25_slope,
        low_52w, high_52w,
    )

    timing_label = timing_label_from_score(
        t_score, is_downtrend, high_price_alert
    )

    # ---------------------------------------------------------
    # ⑨ 総合QVTスコア
    # ---------------------------------------------------------
    qvt_score = round((q_score + v_score + t_score) / 3, 1)

    # ---------------------------------------------------------
    # ⑩ すべて返す
    # ---------------------------------------------------------
    return {
        "df": df,
        "df_valid": df_valid,
        "price": price,
        "ma25": ma25, "ma50": ma50, "ma75": ma75,
        "rsi": rsi,
        "bb_upper1": bb_upper1, "bb_upper2": bb_upper2,
        "bb_lower1": bb_lower1, "bb_lower2": bb_lower2,
        "ma25_slope": ma25_slope,
        "arrow25": arrow25,
        "arrow50": arrow50,
        "arrow75": arrow75,

        # 判定
        "bb_text": bb_text,
        "bb_icon": bb_icon,
        "bb_strength": bb_strength,
        "signal_text": signal_text,
        "signal_icon": signal_icon,
        "signal_strength": signal_strength,

        "highprice_score": highprice_score,
        "low_score": low_score,
        "is_flat": is_flat,
        "slope_ok": slope_ok,

        # 財務
        "per": per, "pbr": pbr,
        "eps": eps, "bps": bps,
        "eps_fwd": eps_fwd,
        "per_fwd": per_fwd_calc,
        "roe": roe, "roa": roa,
        "equity_ratio": equity_ratio,
        "dividend_yield": dividend_yield,

        # スコア
        "q_score": q_score,
        "v_score": v_score,
        "t_score": t_score,
        "qvt_score": qvt_score,
        "timing_label": timing_label,
        "high_price_alert": high_price_alert,
        "t_mode": t_mode,
    }
