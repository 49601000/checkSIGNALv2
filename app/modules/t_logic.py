"""
t_logic.py

タイミングロジック（押し目判定 / BB判定 / Tスコア計算）。
テクニカル指標そのものは indicators.py に委ね、
本モジュールでは「どう解釈するか」を担当する。

- BB 判定（テキスト＋アイコン＋強度）
- 高値圏 / 逆張りスコア
- 押し目シグナル
- T スコア
- T モード（順張り / 逆張り）とラベル
"""

from typing import Tuple, Optional, Dict, Any


# -----------------------------------------------------------
# BB テキスト判定
# -----------------------------------------------------------


def judge_bb_signal(
    price: float,
    bb_plus1: float,
    bb_plus2: float,
    bb_minus1: float,
    bb_minus2: float,
) -> Tuple[str, str, int]:
    if price >= bb_plus2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb_plus1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bb_minus2:
        return "過度に売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bb_minus1:
        return "売られ気味（-1σ以下）", "📉", 2
    return "平均圏（±1σ内）", "⚪️", 1


# -----------------------------------------------------------
# 高値圏スコア
# -----------------------------------------------------------


def is_high_price_zone(
    price: float,
    ma_25: float,
    ma_50: float,
    bb_plus1: float,
    rsi: Optional[float],
    per: Optional[float],
    pbr: Optional[float],
    high_52w: Optional[float],
) -> int:
    score = 0

    if price <= ma_25 * 1.10 and price <= ma_50 * 1.10:
        score += 20
    if price <= bb_plus1:
        score += 20
    if rsi is not None and rsi < 70:
        score += 15
    if high_52w and price < high_52w * 0.95:
        score += 15

    # per / pbr を使った追加ロジックを入れたくなればここに足す余地あり
    return score


# -----------------------------------------------------------
# 逆張りスコア
# -----------------------------------------------------------


def is_low_price_zone(
    price: float,
    ma_25: float,
    ma_50: float,
    bb_minus1: float,
    bb_minus2: float,
    rsi: Optional[float],
    per: Optional[float],
    pbr: Optional[float],
    low_52w: Optional[float],
) -> int:
    score = 0

    if price < ma_25 * 0.90 and price < ma_50 * 0.90:
        score += 20
    if price < bb_minus1:
        score += 15
    if price < bb_minus2:
        score += 20
    if rsi is not None and rsi < 30:
        score += 15
    if low_52w and price <= low_52w * 1.05:
        score += 15

    return score


# -----------------------------------------------------------
# MA がフラットに近いか判定
# -----------------------------------------------------------


def is_flat_ma(
    ma_25: float,
    ma_50: float,
    ma_75: float,
    tolerance: float = 0.03,
) -> bool:
    ma_values = [ma_25, ma_50, ma_75]
    if min(ma_values) == 0:
        return False
    return (max(ma_values) - min(ma_values)) / max(ma_values) <= tolerance


# -----------------------------------------------------------
# 押し目シグナル（軽い/そこそこ/強い）
# -----------------------------------------------------------


def judge_signal(
    price: float,
    ma_25: float,
    ma_50: float,
    ma_75: float,
    bb_minus1: float,
    bb_plus1: float,
    bb_minus2: float,
    rsi: Optional[float],
    high_52w: Optional[float],
    low_52w: Optional[float],
) -> Tuple[str, str, int]:

    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma_75 and rsi < 40 and price <= bb_minus1:
        return "バーゲン（強い押し目）", "🔴", 3

    elif (price <= ma_75 and price < bb_minus1) or (rsi < 30 and price < bb_minus1):
        return "そこそこ押し目", "🟠", 2

    elif price < ma_25 * 0.97 and rsi < 37.5 and price <= bb_minus1:
        return "軽い押し目", "🟡", 1

    elif is_high_price_zone(
        price, ma_25, ma_50, bb_plus1, rsi, None, None, high_52w
    ) <= 40:
        return "高値圏（要注意！）", "🔥", 0

    return "押し目シグナルなし", "🟢", 0


# -----------------------------------------------------------
# Tスコア本体（0〜100）
# -----------------------------------------------------------


def calc_timing_score(
    price: float,
    rsi: Optional[float],
    bb_plus1: float,
    bb_plus2: float,
    bb_minus1: float,
    bb_minus2: float,
    ma_25: float,
    ma_50: float,
    ma_75: float,
    slope_25: float,
    low_52w: Optional[float],
    high_52w: Optional[float],
) -> float:

    t = 50.0  # ニュートラル

    # RSI
    if rsi is not None:
        t += (50 - rsi) * 0.6  # RSI低いほどプラス

    # BBとの位置
    if price <= bb_minus2:
        t += 20
    elif price <= bb_minus1:
        t += 10
    elif price >= bb_plus2:
        t -= 20
    elif price >= bb_plus1:
        t -= 10

    # 52週レンジ内の位置
    if low_52w and high_52w and high_52w > low_52w:
        pos = (price - low_52w) / (high_52w - low_52w)
        t += (0.5 - pos) * 40  # 下寄りほどプラス

    # MAの下にどれだけ潜っているか
    below_mas = sum(
        [
            price < ma_25,
            price < ma_50,
            price < ma_75,
        ]
    )
    t += below_mas * 5

    # 傾き
    if slope_25 <= -1.0:
        t -= 15
    elif slope_25 < 0:
        t -= 5
    elif slope_25 >= 1.0:
        t += 5

    return float(max(0, min(100, round(t, 1))))


# -----------------------------------------------------------
# Tモード表示用ラベル
# -----------------------------------------------------------


def timing_label_from_score(
    t_score: float,
    is_downtrend: bool,
    high_price_alert: bool,
) -> str:

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


# -----------------------------------------------------------
# まとめ用：Tメトリクス一括計算
# -----------------------------------------------------------


def compute_t_metrics(
    price: float,
    ma_25: float,
    ma_50: float,
    ma_75: float,
    rsi: Optional[float],
    bb_plus1: float,
    bb_plus2: float,
    bb_minus1: float,
    bb_minus2: float,
    slope_25: float,
    low_52w: Optional[float],
    high_52w: Optional[float],
    per: Optional[float] = None,
    pbr: Optional[float] = None,
) -> Dict[str, Any]:
    """
    indicators.compute_indicators から呼び出される、
    「T 周りの値を全部まとめて返す」ヘルパー。
    """

    # MA傾きからのフラグ
    slope_ok = slope_25 < 0
    is_flat_or_gentle_up = (abs(slope_25) <= 0.3) and (slope_25 >= 0)

    # BB・押し目
    bb_text, bb_icon, bb_strength = judge_bb_signal(
        price, bb_plus1, bb_plus2, bb_minus1, bb_minus2
    )

    signal_text, signal_icon, signal_strength = judge_signal(
        price,
        ma_25,
        ma_50,
        ma_75,
        bb_minus1,
        bb_plus1,
        bb_minus2,
        rsi,
        high_52w,
        low_52w,
    )

    # 高値掴みアラート
    high_price_alert = False
    if (
        price >= bb_plus1
        or (high_52w not in (None, 0) and price >= high_52w * 0.98)
        or (rsi is not None and rsi >= 70)
    ):
        high_price_alert = True

    # 順張り / 逆張りスコア
    highprice_score = is_high_price_zone(
        price, ma_25, ma_50, bb_plus1, rsi, per, pbr, high_52w
    )
    low_score = is_low_price_zone(
        price, ma_25, ma_50, bb_minus1, bb_minus2, rsi, per, pbr, low_52w
    )

    trend_conditions = [
        ma_75 < ma_50 < ma_25,
        is_flat_or_gentle_up,
        highprice_score >= 60,
    ]
    trend_ok = sum(trend_conditions)
    trend_comment = [
        "現時点では見送りが妥当です。",
        "慎重に検討すべき状況です。",
        "買い検討の余地があります。",
        "買い候補として非常に魅力的です。",
    ][trend_ok]

    contrarian_conditions = [
        (ma_75 > ma_50 > ma_25) or is_flat_ma(ma_25, ma_50, ma_75),
        slope_ok,
        low_score >= 60,
    ]
    contr_ok = sum(contrarian_conditions)
    contr_comment = [
        "現時点では見送りが妥当です。",
        "慎重に検討すべき状況です。",
        "買い検討の余地があります。",
        "買い候補として非常に魅力的です。",
    ][contr_ok]

    # Tスコア本体
    t_score = calc_timing_score(
        price=price,
        rsi=rsi,
        bb_plus1=bb_plus1,
        bb_plus2=bb_plus2,
        bb_minus1=bb_minus1,
        bb_minus2=bb_minus2,
        ma_25=ma_25,
        ma_50=ma_50,
        ma_75=ma_75,
        slope_25=slope_25,
        low_52w=low_52w,
        high_52w=high_52w,
    )

    # 順張り/逆張りモード
    if ma_25 > ma_50 > ma_75:
        t_mode = "trend"
    else:
        t_mode = "contrarian"

    is_downtrend = bool(ma_75 > ma_50 > ma_25 and slope_25 < 0)

    timing_label = timing_label_from_score(
        t_score=t_score,
        is_downtrend=is_downtrend,
        high_price_alert=high_price_alert,
    )

    return {
        # Tスコア周り
        "t_score": t_score,
        "t_mode": t_mode,
        "timing_label": timing_label,
        "high_price_alert": high_price_alert,

        # BB判定
        "bb_text": bb_text,
        "bb_icon": bb_icon,
        "bb_strength": bb_strength,

        # 押し目シグナル
        "signal_text": signal_text,
        "signal_icon": signal_icon,
        "signal_strength": signal_strength,

        # 高値/安値スコア
        "highprice_score": highprice_score,
        "low_score": low_score,

        # 順張り/逆張り条件とコメント
        "trend_conditions": trend_conditions,
        "trend_comment": trend_comment,
        "contrarian_conditions": contrarian_conditions,
        "contr_comment": contr_comment,

        # 補助フラグ
        "slope_25": slope_25,
        "slope_ok": slope_ok,
        "is_flat_or_gentle_up": is_flat_or_gentle_up,
    }
