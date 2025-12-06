# indicators.py
from typing import Optional
import pandas as pd


def slope_arrow(series: pd.Series, window: int = 3) -> str:
    """MA の向きを矢印で返す（↗ / ↘ / →）"""
    series = series.dropna()
    if len(series) < window + 1:
        return "→"
    recent = series.iloc[-window:]
    diff = recent.iloc[-1] - recent.iloc[0]
    if diff > 0:
        return "↗"
    elif diff < 0:
        return "↘"
    else:
        return "→"


def judge_bb_signal(price, bb1, bb2, bbm1, bbm2):
    """ボリンジャーバンド位置のテキスト判定"""
    if price >= bb2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bbm2:
        return "過度に売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bbm1:
        return "売られ気味（-1σ以下）", "📉", 2
    else:
        return "平均圏（±1σ内）", "⚪️", 1


def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    """
    割高否定スコア（高いほど『割高ではない』方向）
    """
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_upper1:
        score += 20
    if rsi < 70:
        score += 15
    if high_52w != 0 and price < high_52w * 0.95:
        score += 15
    # per / pbr は今は未使用だが将来ロジック追加用に残してある
    return score


def is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2,
                      rsi, per, pbr, low_52w):
    """
    割安スコア（高いほど『割安』方向）
    """
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_lower1:
        score += 15
    if price < bb_lower2:
        score += 20
    if rsi < 30:
        score += 15
    if price <= low_52w * 1.05:
        score += 15
    # per / pbr も必要ならここに加点ロジックを足せる
    return score


def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    """3本のMAがどれくらい接近しているか（フラットかどうか）"""
    ma_values = [ma25, ma50, ma75]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance


def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2,
                 rsi, high_52w, low_52w):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    # --- 強い押し目（バーゲン） ---
    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3

    # --- そこそこ押し目 ---
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2

    # --- 軽い押し目 ---
    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1

    # --- 🔥 高値圏（要注意！） ---
    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi,
                            None, None, high_52w) <= 40:
        return "高値圏（要注意！）", "🔥", 0

    # --- 押し目なし ---
    else:
        return "押し目シグナルなし", "🟢", 0


def compute_indicators(
    df: pd.DataFrame,
    close_col: str,
    high_52w: float,
    low_52w: float,
    eps: Optional[float] = None,
    bps: Optional[float] = None,
    eps_fwd: Optional[float] = None,
    per_fwd: Optional[float] = None,
):
    """
    df に各種テクニカル指標を追加し、判定に必要な値をまとめて返す。
    ここで EPS/BPS から PER/PBR を計算する。
    """
    # 終値（最新）
    price = float(df[close_col].iloc[-1])

    # === 移動平均 ===
    df["25MA"] = df[close_col].rolling(25).mean()
    df["50MA"] = df[close_col].rolling(50).mean()
    df["75MA"] = df[close_col].rolling(75).mean()

    # === ボリンジャーバンド ===
    df["20MA"] = df[close_col].rolling(20).mean()
    df["20STD"] = df[close_col].rolling(20).std()
    df["BB_+1σ"] = df["20MA"] + df["20STD"]
    df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
    df["BB_-1σ"] = df["20MA"] - df["20STD"]
    df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]

    # === RSI ===
    delta = df[close_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, 1e-10)
    df["RSI"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

    # 有効データ
    df_valid = df.dropna()
    if df_valid.empty or len(df_valid) < 5:
        raise ValueError("テクニカル指標を計算するためのデータが不足しています。")

    last = df_valid.iloc[-1]

    ma25, ma50, ma75 = last["25MA"], last["50MA"], last["75MA"]
    rsi = last["RSI"]
    bb_upper1, bb_upper2 = last["BB_+1σ"], last["BB_+2σ"]
    bb_lower1, bb_lower2 = last["BB_-1σ"], last["BB_-2σ"]

    # === MA の傾き ===
    ma25_series = df["25MA"].dropna()
    if len(ma25_series) >= 4:
        ma25_slope = (ma25_series.iloc[-1] - ma25_series.iloc[-4]) / ma25_series.iloc[-4] * 100
    else:
        ma25_slope = 0.0

    slope_ok = ma25_slope < 0          # 逆張り条件
    is_flat_or_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0  # 順張り条件

    arrow25 = slope_arrow(df["25MA"])
    arrow50 = slope_arrow(df["50MA"])
    arrow75 = slope_arrow(df["75MA"])

    # === PER / PBR 計算 ===
    #実績 PER
    per: Optional[float] = None
    pbr: Optional[float] = None
    if eps not in (None, 0):
        per = price / eps
    if bps not in (None, 0):
        pbr = price / bps
    # 予想 PER（IRBANK にある数字を優先し、なければ eps_fwd から計算）
    per_fwd_calc = None
    if per_fwd not in (None, 0):
        per_fwd_calc = per_fwd
    elif eps_fwd not in (None, 0):
        per_fwd_calc = price / eps_fwd

    # === BB 判定 ===
    bb_text, bb_icon, bb_strength = judge_bb_signal(
        price, bb_upper1, bb_upper2, bb_lower1, bb_lower2
    )

    # === 押し目シグナル判定 ===
    signal_text, signal_icon, signal_strength = judge_signal(
        price,
        ma25, ma50, ma75,
        bb_lower1, bb_upper1, bb_lower2,
        rsi, high_52w, low_52w,
    )

    # === 順張り・逆張りスコア ===
    highprice_score = is_high_price_zone(
        price, ma25, ma50, bb_upper1, rsi,
        per, pbr, high_52w
    )
    low_score = is_low_price_zone(
        price, ma25, ma50, bb_lower1, bb_lower2, rsi,
        per, pbr, low_52w
    )

    trend_conditions = [
        ma75 < ma50 < ma25,
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
        (ma75 > ma50 > ma25) or is_flat_ma(ma25, ma50, ma75),
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

    return {
        "df": df,
        "df_valid": df_valid,
        "price": price,
        "ma25": ma25,
        "ma50": ma50,
        "ma75": ma75,
        "rsi": rsi,
        "bb_upper1": bb_upper1,
        "bb_upper2": bb_upper2,
        "bb_lower1": bb_lower1,
        "bb_lower2": bb_lower2,
        "ma25_slope": ma25_slope,
        "slope_ok": slope_ok,
        "is_flat_or_gentle_up": is_flat_or_gentle_up,
        "arrow25": arrow25,
        "arrow50": arrow50,
        "arrow75": arrow75,
        "bb_text": bb_text,
        "bb_icon": bb_icon,
        "bb_strength": bb_strength,
        "signal_text": signal_text,
        "signal_icon": signal_icon,
        "signal_strength": signal_strength,
        "highprice_score": highprice_score,
        "low_score": low_score,
        "trend_conditions": trend_conditions,
        "trend_comment": trend_comment,
        "contrarian_conditions": contrarian_conditions,
        "contr_comment": contr_comment,
        "eps": eps,
        "bps": bps,
        "per": per,
        "pbr": pbr,
    }
