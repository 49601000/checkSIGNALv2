# indicators.py
from typing import Optional
import pandas as pd


# ==========================
# 共通ユーティリティ
# ==========================
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
    割高否定スコア（高いほど『割高ではない』方向） 0〜70点
    """
    score = 0
    # 株価が25・50MAより +10% 未満
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    # BB +1σ 以下
    if price <= bb_upper1:
        score += 20
    # RSI < 70
    if rsi < 70:
        score += 15
    # 52週高値の 95% 未満
    if high_52w != 0 and price < high_52w * 0.95:
        score += 15
    return score  # 最大 70 点想定


def is_low_price_zone(
    price,
    ma25,
    ma50,
    bb_lower1,
    bb_lower2,
    rsi,
    per,
    pbr,
    low_52w,
):
    """
    割安スコア（高いほど『割安』方向）0〜85点
    """
    score = 0
    # 株価が25MA/50MAより −10%以上
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    # BB -1σ 以下
    if price < bb_lower1:
        score += 15
    # BB -2σ 以下
    if price < bb_lower2:
        score += 20
    # RSI < 30
    if rsi < 30:
        score += 15
    # 52週安値の 105% 以内
    if price <= low_52w * 1.05:
        score += 15
    return score  # 最大 85 点想定


def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    """3本のMAがどれくらい接近しているか（フラットかどうか）"""
    ma_values = [ma25, ma50, ma75]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance


def judge_signal(
    price,
    ma25,
    ma50,
    ma75,
    bb_lower1,
    bb_upper1,
    bb_lower2,
    rsi,
    high_52w,
    low_52w,
):

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
    elif is_high_price_zone(
        price,
        ma25,
        ma50,
        bb_upper1,
        rsi,
        None,
        None,
        high_52w,
    ) <= 40:
        return "高値圏（要注意！）", "🔥", 0

    # --- 押し目なし ---
    else:
        return "押し目シグナルなし", "🟢", 0


# ==========================
# Q: ビジネスの質スコア
# ==========================
def _score_quality(
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
) -> dict:
    """
    Q: ROE / ROA / 自己資本比率から 0〜100点の「ビジネスの質」スコアを算出
    ROE: 最大50点, ROA: 最大30点, 自己資本比率: 最大20点
    """
    # --- ROE (％) 0〜50点 ---
    roe_score = 0.0
    if roe is not None:
        if roe <= 0:
            roe_score = 0
        elif roe < 5:
            roe_score = 10
        elif roe < 10:
            roe_score = 20
        elif roe < 15:
            roe_score = 30
        elif roe < 20:
            roe_score = 40
        else:
            roe_score = 50  # 20%以上は満点

    # --- ROA (％) 0〜30点 ---
    roa_score = 0.0
    if roa is not None:
        if roa <= 0:
            roa_score = 0
        elif roa < 2:
            roa_score = 10
        elif roa < 5:
            roa_score = 20
        elif roa < 8:
            roa_score = 25
        else:
            roa_score = 30  # 8%以上は満点

    # --- 自己資本比率 (％) 0〜20点 ---
    eq_score = 0.0
    if equity_ratio is not None:
        if equity_ratio < 20:
            eq_score = 0
        elif equity_ratio < 30:
            eq_score = 5
        elif equity_ratio < 40:
            eq_score = 10
        elif equity_ratio < 50:
            eq_score = 15
        else:
            eq_score = 20  # 50%以上は満点

    q_score = roe_score + roa_score + eq_score
    q_score = max(0.0, min(100.0, q_score))

    return {
        "q_score": q_score,
        "q_roe_score": roe_score,
        "q_roa_score": roa_score,
        "q_equity_score": eq_score,
    }


# ==========================
# V: バリュエーションスコア
# ==========================
def _score_valuation(
    per: Optional[float],
    pbr: Optional[float],
    dividend_yield: Optional[float],
) -> dict:
    """
    PER / PBR / 配当利回りから 0〜100点のバリュエーションスコアを算出
    PER: 最大30点, PBR: 最大30点, 配当: 最大40点
    """
    # --- PER 0〜30点 ---
    per_score = 0.0
    if per is not None and per > 0:
        if per < 8:
            per_score = 30
        elif per < 15:
            per_score = 25
        elif per < 25:
            per_score = 15
        elif per < 40:
            per_score = 5
        else:
            per_score = 0
    # None の場合は 0点

    # --- PBR 0〜30点 ---
    pbr_score = 0.0
    if pbr is not None and pbr > 0:
        if pbr < 1.0:
            pbr_score = 30
        elif pbr < 2.0:
            pbr_score = 20
        elif pbr < 3.0:
            pbr_score = 10
        else:
            pbr_score = 0

    # --- 配当利回り 0〜40点 ---
    div_score = 0.0
    if dividend_yield is not None and dividend_yield >= 0:
        if dividend_yield >= 4.0:
            div_score = 40
        elif dividend_yield >= 2.0:
            div_score = 25
        elif dividend_yield >= 1.0:
            div_score = 10
        else:
            div_score = 0

    v_score = per_score + pbr_score + div_score
    v_score = max(0.0, min(100.0, v_score))

    return {
        "v_score": v_score,
        "v_per_score": per_score,
        "v_pbr_score": pbr_score,
        "v_div_score": div_score,
    }


# ==========================
# T: タイミングスコア
# ==========================
def _score_timing_trend(
    price: float,
    ma25: float,
    ma50: float,
    rsi: float,
    highprice_score: float,
) -> dict:
    """
    順張りモード用: highprice_score + MA乖離 + RSI から T を算出
    """
    # 1. 安全度（割高否定）0〜50
    safety = min(highprice_score, 70.0) / 70.0 * 50.0

    # 2. 位置（25MA からの乖離）0〜30
    dist = abs(price - ma25) / ma25 if ma25 > 0 else 1.0
    if dist <= 0.02:       # 2%以内 → ベスト
        place = 30.0
    elif dist <= 0.05:     # 5%以内 → 許容
        place = 15.0
    else:                  # それ以上乖離 → タイミング微妙
        place = 0.0

    # 3. 勢い（RSI の心地よさ）0〜20
    if 45.0 <= rsi <= 60.0:
        momentum = 20.0
    elif 40.0 <= rsi <= 65.0:
        momentum = 10.0
    else:
        momentum = 0.0

    t_score = safety + place + momentum
    t_score = max(0.0, min(100.0, t_score))

    return {
        "t_score": t_score,
        "t_mode": "trend",
        "t_safety": safety,
        "t_placement": place,
        "t_momentum": momentum,
    }


def _score_timing_contrarian(
    price: float,
    ma25: float,
    ma50: float,
    bb_lower1: float,
    bb_lower2: float,
    rsi: float,
    low_score: float,
) -> dict:
    """
    逆張りモード用: low_score + 価格の位置 + RSI から T を算出
    """
    # 1. 安全度（下値余地の小ささ）0〜50
    safety = min(low_score, 85.0) / 85.0 * 50.0

    # 2. 位置（どれだけ押し目ゾーンか）0〜30
    if price <= bb_lower2:
        place = 30.0   # −2σ 以下 → 強い押し目
    elif price <= bb_lower1:
        place = 20.0   # −1σ 以下
    elif price < ma25 and price < ma50:
        place = 10.0   # MA の下だが BB 圏内
    else:
        place = 0.0

    # 3. 勢い（リバウンド初動かどうか）0〜20
    if rsi <= 25.0:
        momentum = 5.0   # まだ売られすぎ
    elif 25.0 < rsi <= 40.0:
        momentum = 20.0  # 売られすぎ→戻り初動
    else:
        momentum = 0.0

    t_score = safety + place + momentum
    t_score = max(0.0, min(100.0, t_score))

    return {
        "t_score": t_score,
        "t_mode": "contrarian",
        "t_safety": safety,
        "t_placement": place,
        "t_momentum": momentum,
    }


# ==========================
# メイン: 各種指標 + QVT スコア
# ==========================
def compute_indicators(
    df: pd.DataFrame,
    close_col: str,
    high_52w: float,
    low_52w: float,
    ticker: Optional[str] = None,  # いまは未使用。将来拡張用に残しておく。
    eps: Optional[float] = None,
    bps: Optional[float] = None,
    eps_fwd: Optional[float] = None,
    per_fwd: Optional[float] = None,
    roe: Optional[float] = None,
    roa: Optional[float] = None,
    equity_ratio: Optional[float] = None,
    dividend_yield: Optional[float] = None,
):
    """
    df に各種テクニカル指標を追加し、判定に必要な値＆
    Q/V/T スコアをまとめて返す。
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

    ma25, ma50, ma75 = last["25MA"], last["50MA"], last["75MA"]
    rsi = last["RSI"]
    bb_upper1, bb_upper2 = last["BB_+1σ"], last["BB_+2σ"]
    bb_lower1, bb_lower2 = last["BB_-1σ"], last["BB_-2σ"]

    # === MA の傾き ===
    ma25_series = df["25MA"].dropna()
    if len(ma25_series) >= 4:
        ma25_slope = (
            (ma25_series.iloc[-1] - ma25_series.iloc[-4])
            / ma25_series.iloc[-4]
            * 100
        )
    else:
        ma25_slope = 0.0

    slope_ok = ma25_slope < 0  # 逆張り条件
    is_flat_or_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0  # 順張り条件

    arrow25 = slope_arrow(df["25MA"])
    arrow50 = slope_arrow(df["50MA"])
    arrow75 = slope_arrow(df["75MA"])

    # === PER / PBR 計算 ===
    per: Optional[float] = None
    pbr: Optional[float] = None
    if eps not in (None, 0):
        per = price / eps
    if bps not in (None, 0):
        pbr = price / bps

    # 予想 PER（per_fwd を優先し、無ければ eps_fwd から計算）
    per_fwd_calc: Optional[float] = None
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
        ma25,
        ma50,
        ma75,
        bb_lower1,
        bb_upper1,
        bb_lower2,
        rsi,
        high_52w,
        low_52w,
    )

    # === 順張り・逆張りスコア（元々のブル／ベアスコア） ===
    highprice_score = is_high_price_zone(
        price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w
    )
    low_score = is_low_price_zone(
        price,
        ma25,
        ma50,
        bb_lower1,
        bb_lower2,
        rsi,
        per,
        pbr,
        low_52w,
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

    # ==========================
    # Q / V / T スコアの算出
    # ==========================
    q_info = _score_quality(roe=roe, roa=roa, equity_ratio=equity_ratio)
    v_info = _score_valuation(per=per, pbr=pbr, dividend_yield=dividend_yield)

    # T は「順張り/逆張り」で場合分け
    if trend_conditions[0]:
        t_info = _score_timing_trend(
            price=price,
            ma25=ma25,
            ma50=ma50,
            rsi=rsi,
            highprice_score=highprice_score,
        )
    else:
        t_info = _score_timing_contrarian(
            price=price,
            ma25=ma25,
            ma50=ma50,
            bb_lower1=bb_lower1,
            bb_lower2=bb_lower2,
            rsi=rsi,
            low_score=low_score,
        )

    q_score = q_info["q_score"]
    v_score = v_info["v_score"]
    t_score = t_info["t_score"]
    qvt_total = (q_score + v_score + t_score) / 3.0

    # 返却
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
        "eps_fwd": eps_fwd,
        "per_fwd": per_fwd_calc,
        # Q
        "roe": roe,
        "roa": roa,
        "equity_ratio": equity_ratio,
        **q_info,
        # V
        "dividend_yield": dividend_yield,
        **v_info,
        # T
        **t_info,
        # 総合
        "qvt_total": qvt_total,
    }
