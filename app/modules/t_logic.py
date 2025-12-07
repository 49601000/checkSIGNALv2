"""
タイミングロジック（押し目判定 / BB判定 / Tスコア計算）
テクニカル指標そのものは indicators.py に委ね、
本モジュールでは「どう解釈するか」を担当する。
"""

from typing import Tuple, Optional
import pandas as pd


# -----------------------------------------------------------
# BB テキスト判定
# -----------------------------------------------------------

def judge_bb_signal(price, bb1, bb2, bbm1, bbm2):
    if price >= bb2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bbm2:
        return "過度に売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bbm1:
        return "売られ気味（-1σ以下）", "📉", 2
    return "平均圏（±1σ内）", "⚪️", 1


# -----------------------------------------------------------
# 高値圏スコア
# -----------------------------------------------------------

def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_upper1:
        score += 20
    if rsi < 70:
        score += 15
    if high_52w and price < high_52w * 0.95:
        score += 15
    return score


# -----------------------------------------------------------
# 逆張りスコア
# -----------------------------------------------------------

def is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_lower1:
        score += 15
    if price < bb_lower2:
        score += 20
    if rsi < 30:
        score += 15
    if low_52w and price <= low_52w * 1.05:
        score += 15
    return score


# -----------------------------------------------------------
# MA がフラットに近いか判定
# -----------------------------------------------------------

def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    ma_values = [ma25, ma50, ma75]
    if min(ma_values) == 0:
        return False
    return (max(ma_values) - min(ma_values)) / max(ma_values) <= tolerance


# -----------------------------------------------------------
# 押し目シグナル（軽い/そこそこ/強い）
# -----------------------------------------------------------

def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2, rsi, high_52w, low_52w):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3

    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2

    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1

    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, None, None, high_52w) <= 40:
        return "高値圏（要注意！）", "🔥", 0

    return "押し目シグナルなし", "🟢", 0


# -----------------------------------------------------------
# Tスコア本体（0〜100）
# -----------------------------------------------------------

def calc_timing_score(
    price,
    rsi,
    bb_upper1,
    bb_upper2,
    bb_lower1,
    bb_lower2,
    ma25,
    ma50,
    ma75,
    ma25_slope,
    low_52w,
    high_52w,
) -> float:

    t = 50.0  # ニュートラル

    if rsi is not None:
        t += (50 - rsi) * 0.6

    if price <= bb_lower2:
        t += 20
    elif price <= bb_lower1:
        t += 10
    elif price >= bb_upper2:
        t -= 20
    elif price >= bb_upper1:
        t -= 10

    if low_52w and high_52w and high_52w > low_52w:
        pos = (price - low_52w) / (high_52w - low_52w)
        t += (0.5 - pos) * 40

    below_mas = sum([
        price < ma25,
        price < ma50,
        price < ma75,
    ])
    t += below_mas * 5

    if ma25_slope <= -1.0:
        t -= 15
    elif ma25_slope < 0:
        t -= 5
    elif ma25_slope >= 1.0:
        t += 5

    return float(max(0, min(100, round(t, 1))))


# -----------------------------------------------------------
# Tモード表示用ラベル
# -----------------------------------------------------------

def timing_label_from_score(t_score, is_downtrend, high_price_alert):

    if t_score <= 30:
        if is_downtrend:
            return "落ちるナイフ（要注意）"
        elif high_price_alert:
            return "高値圏（要注意）"
        return "タイミング悪化（要注意）"

    elif t_score <= 50:
        return "押し目シグナルなし〜様子見"

    elif t_score <= 80:
        return "そこそこ押し目"

    return "バーゲン（強い押し目）"
