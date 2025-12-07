from typing import Optional, Dict, Any
import pandas as pd


# ============================================================
# ユーティリティ
# ============================================================

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


# ============================================================
# 価格ゾーンスコア（旧ブル／ベアスコア）
# ============================================================

def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    """
    割高否定スコア（高いほど『割高ではない』方向）
    → トレンド判定や解説用
    """
    score = 0
    # 株価が25MA・50MAより +10% 未満 → OK
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    # BB +1σ 以下 → OK
    if price <= bb_upper1:
        score += 20
    # RSI 70 未満 → OK
    if rsi < 70:
        score += 15
    # 52週高値の95% 未満 → OK
    if high_52w != 0 and price < high_52w * 0.95:
        score += 15
    # per / pbr は現状ロジックに未使用（拡張フック）
    return score


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
    割安スコア（高いほど『割安』方向）
    → 逆張り側の解説用
    """
    score = 0
    # 株価が 25MA・50MA より -10% 以下
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
    if low_52w is not None and low_52w != 0:
        if price <= low_52w * 1.05:
            score += 15
    # per / pbr は現状ロジックに未使用（拡張フック）
    return score


def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    """3本のMAがどれくらい接近しているか（フラットかどうか）"""
    ma_values = [ma25, ma50, ma75]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance


# ============================================================
# 押し目シグナル（既存ロジック）
# ============================================================

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


# ============================================================
# Q（ビジネスの質）スコア
# ============================================================

def _score_quality(
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
) -> float:
    """
    ROE / ROA / 自己資本比率から 0〜100 に正規化した Q スコアを計算。
    “高すぎるレバレッジで ROE を盛る”ケースは、自己資本比率が低いと点が伸びにくい形で調整。
    """
    raw = 0.0
    max_raw = 50.0 + 25.0 + 20.0  # ROE(50) + ROA(25) + Equity(20) = 95

    # --- ROE ---
    if roe is not None:
        if roe <= 0:
            raw += 0
        elif roe < 5:
            raw += 10
        elif roe < 10:
            raw += 20
        elif roe < 15:
            raw += 30
        elif roe < 20:
            raw += 40
        elif roe < 25:
            raw += 45
        else:
            raw += 50  # 25%以上はかなり優秀

    # --- ROA ---
    if roa is not None:
        if roa <= 0:
            raw += 0
        elif roa < 2:
            raw += 5
        elif roa < 4:
            raw += 10
        elif roa < 6:
            raw += 15
        elif roa < 8:
            raw += 20
        else:
            raw += 25  # 8%以上はかなり優秀

    # --- 自己資本比率 ---
    if equity_ratio is not None:
        if equity_ratio < 20:
            raw += 0
        elif equity_ratio < 30:
            raw += 3
        elif equity_ratio < 40:
            raw += 6
        elif equity_ratio < 50:
            raw += 10
        elif equity_ratio < 60:
            raw += 15
        else:
            raw += 20  # 60%以上はかなり堅め

    if max_raw == 0:
        return 0.0

    return max(0.0, min(100.0, raw / max_raw * 100.0))


# ============================================================
# V（バリュエーション）スコア
# ============================================================

def _score_valuation(
    per: Optional[float],
    pbr: Optional[float],
    dividend_yield: Optional[float],
) -> float:
    """
    PER / PBR / 配当利回りから 0〜100 に正規化した V スコアを計算。
    ざっくり「割安・そこそこ・普通・やや割高・高すぎ」の段階評価。
    """
    raw = 0.0
    max_raw = 30.0 + 25.0 + 20.0  # PER(30) + PBR(25) + Yield(20) = 75

    # --- PER ---
    if per is not None and per > 0:
        if per < 8:
            raw += 30
        elif per < 12:
            raw += 26
        elif per < 20:
            raw += 20
        elif per < 30:
            raw += 10
        elif per < 40:
            raw += 5
        else:
            raw += 0

    # --- PBR ---
    if pbr is not None and pbr > 0:
        if pbr < 0.8:
            raw += 25
        elif pbr < 1.2:
            raw += 20
        elif pbr < 2.0:
            raw += 10
        elif pbr < 3.0:
            raw += 5
        else:
            raw += 0

    # --- 配当利回り ---
    if dividend_yield is not None and dividend_yield > 0:
        if dividend_yield >= 5:
            raw += 20
        elif dividend_yield >= 3:
            raw += 16
        elif dividend_yield >= 2:
            raw += 10
        elif dividend_yield >= 1:
            raw += 5
        else:
            raw += 0

    if max_raw == 0:
        return 0.0

    return max(0.0, min(100.0, raw / max_raw * 100.0))


# ============================================================
# T（タイミング）スコア
#  - 純テクニカル（RSI / BB / 52週レンジ / MA位置 / MA傾き）だけで算出
#  - PER / PBR / 配当利回りは使わない（Q / V に委ねる）
#  - 下落トレンドかつ低スコアは「落ちるナイフ（要注意）」表示
# ============================================================

def _calc_timing_score(
    price: float,
    rsi: Optional[float],
    bb_upper1: float,
    bb_upper2: float,
    bb_lower1: float,
    bb_lower2: float,
    ma25: float,
    ma50: float,
    ma75: float,
    ma25_slope: float,
    low_52w: float,
    high_52w: float,
) -> float:
    """
    タイミングスコア T（0〜100）を計算する。
    50 = 中立。高いほど「押し目寄り」、低いほど「高値寄り or タイミング悪い」。
    """
    # ベースはニュートラル 50
    t = 50.0

    # ① RSI：50 からのズレを素直に反映（低いほどプラス、高いほどマイナス）
    if rsi is not None:
        t += (50.0 - rsi) * 0.6  # RSI=20 → +18, RSI=80 → -18

    # ② ボリンジャーバンド位置
    if price <= bb_lower2:
        t += 20.0
    elif price <= bb_lower1:
        t += 10.0
    elif price >= bb_upper2:
        t -= 20.0
    elif price >= bb_upper1:
        t -= 10.0

    # ③ 52週レンジ内の位置（0=安値, 1=高値）
    if (
        low_52w is not None
        and high_52w is not None
        and high_52w > low_52w
    ):
        pos = (price - low_52w) / (high_52w - low_52w)
        # 中央(0.5)から外れるほどマイナス／プラス（安値側にいるとプラス）
        t += (0.5 - pos) * 40.0  # 最大 ±20

    # ④ MAとの位置：複数本割っていれば「押し目寄り」として加点
    below_mas = sum([
        price < ma25 if ma25 is not None else 0,
        price < ma50 if ma50 is not None else 0,
        price < ma75 if ma75 is not None else 0,
    ])
    t += below_mas * 5.0  # 最大 +15

    # ⑤ 25MA の傾き：強い下落トレンドは少し減点（落ちるナイフ警戒）
    if ma25_slope is not None:
        if ma25_slope <= -1.0:
            t -= 15.0
        elif ma25_slope < 0:
            t -= 5.0
        elif ma25_slope >= 1.0:
            # 強い上昇トレンドで押し目を狙うときの「ご褒美」少し加点
            t += 5.0

    # クリップ
    t = max(0.0, min(100.0, t))
    return float(round(t, 1))


def _timing_label_from_score(
    t_score: float,
    is_downtrend: bool,
    high_price_alert: bool,
) -> str:
    """
    Tスコアと言語ラベルのマッピング。
    下落トレンドで低スコアなら「落ちるナイフ（要注意）」、
    それ以外の低スコアは「高値圏（要注意）」。
    """
    if t_score <= 30:
        if is_downtrend:
            return "落ちるナイフ（要注意）"
        elif high_price_alert:
            return "高値圏（要注意）"
        else:
            # どちらとも言えないがタイミングが悪いケース
            return "タイミング悪化（要注意）"
    elif t_score <= 50:
        return "押し目シグナルなし〜様子見"
    elif t_score <= 80:
        return "そこそこ押し目"
    else:
        return "バーゲン（強い押し目）"


# ============================================================
# メイン：compute_indicators
# ============================================================

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
) -> Dict[str, Any]:
    """
    df に各種テクニカル指標を追加し、判定に必要な値をまとめて返す。

    - テクニカル系: MA / BB / RSI などはローカル計算
    - ファンダ系: EPS / BPS / ROE / ROA / 自己資本比率 / 配当利回り などは
        外部から渡された値を利用。
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

    # === 高値掴みアラート判定（別途フラグで保持） ===
    high_price_alert = False
    if (
        (price >= bb_upper1)
        or (high_52w and high_52w != 0 and price >= high_52w * 0.98)
        or (rsi is not None and rsi >= 70)
    ):
        high_price_alert = True

    # === 順張り・逆張りスコア（既存のブル／ベアスコア） ===
    highprice_score = is_high_price_zone(
        price, ma25, ma50, bb_upper1, rsi,
        per, pbr, high_52w
    )
    low_score = is_low_price_zone(
        price, ma25, ma50, bb_lower1, bb_lower2,
        rsi, per, pbr, low_52w
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

    # === Q / V スコア ===
    q_score = _score_quality(roe, roa, equity_ratio)
    v_score = _score_valuation(per, pbr, dividend_yield)

    # === T スコア（純テクニカル）===
    t_score = _calc_timing_score(
        price=price,
        rsi=rsi,
        bb_upper1=bb_upper1,
        bb_upper2=bb_upper2,
        bb_lower1=bb_lower1,
        bb_lower2=bb_lower2,
        ma25=ma25,
        ma50=ma50,
        ma75=ma75,
        ma25_slope=ma25_slope,
        low_52w=low_52w,
        high_52w=high_52w,
    )

    # モード（情報として残すだけ）
    if ma25 > ma50 > ma75:
        t_mode = "trend"
    else:
        t_mode = "contrarian"

    # 強い下落トレンドか？
    is_downtrend = bool(ma75 > ma50 > ma25 and ma25_slope < 0)

    timing_label = _timing_label_from_score(
        t_score=t_score,
        is_downtrend=is_downtrend,
        high_price_alert=high_price_alert,
    )

    # 総合 QVT スコア（単純平均）
    qvt_score = (q_score + v_score + t_score) / 3.0

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
        # --- ファンダスコア関連 ---
        "roe": roe,
        "roa": roa,
        "equity_ratio": equity_ratio,
        "dividend_yield": dividend_yield,
        "q_score": q_score,
        "v_score": v_score,
        "t_score": t_score,
        "qvt_score": qvt_score,
        "t_mode": t_mode,
        "timing_label": timing_label,
        "high_price_alert": high_price_alert,
    }
