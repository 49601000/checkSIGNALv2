from typing import Optional
import pandas as pd


# ===========================================================
# 小ヘルパー（スコアリング）
# ===========================================================

def _score_roe(roe: Optional[float]) -> Optional[float]:
    """ROE を 0〜100 点にスコアリング"""
    if roe is None:
        return None
    if roe < 0:
        return 0
    if roe < 5:
        return 20
    if roe < 10:
        return 40
    if roe < 15:
        return 60
    if roe < 20:
        return 80
    return 100  # 20%以上


def _score_roa(roa: Optional[float]) -> Optional[float]:
    """ROA を 0〜100 点にスコアリング（ROEより低めに見る）"""
    if roa is None:
        return None
    if roa < 0:
        return 0
    if roa < 2:
        return 20
    if roa < 4:
        return 40
    if roa < 6:
        return 60
    if roa < 8:
        return 80
    return 100  # 8%以上


def _score_equity_ratio(ratio: Optional[float]) -> Optional[float]:
    """自己資本比率（%）を 0〜100 点にスコアリング"""
    if ratio is None:
        return None
    if ratio < 10:
        return 10
    if ratio < 20:
        return 30
    if ratio < 30:
        return 50
    if ratio < 40:
        return 70
    if ratio < 60:
        return 85
    return 100  # 60%以上（かなり堅い）


def _score_per(per: Optional[float]) -> Optional[float]:
    """PER を 0〜100 点にスコアリング（安いほど高得点）"""
    if per is None or per <= 0:
        return None
    if per < 8:
        return 100
    if per < 12:
        return 85
    if per < 18:
        return 70
    if per < 25:
        return 55
    if per < 40:
        return 35
    return 15  # 40倍以上はかなり割高


def _score_pbr(pbr: Optional[float]) -> Optional[float]:
    """PBR を 0〜100 点にスコアリング（1倍前後を高評価、極端な高PBRは減点）"""
    if pbr is None or pbr <= 0:
        return None
    if pbr < 0.8:
        return 100
    if pbr < 1.2:
        return 85
    if pbr < 2.0:
        return 65
    if pbr < 3.0:
        return 45
    if pbr < 5.0:
        return 25
    return 10  # 5倍以上


def _score_dividend_yield(yld: Optional[float]) -> Optional[float]:
    """配当利回り（%）を 0〜100 点にスコアリング"""
    if yld is None or yld < 0:
        return None
    if yld < 1.0:
        return 20
    if yld < 2.0:
        return 40
    if yld < 3.5:
        return 60
    if yld < 5.0:
        return 80
    if yld < 8.0:
        return 90
    # 8%以上は減配リスクもあるので少し減点
    return 60


def _average_scores(values):
    """None を除外して平均をとる。全て None の場合は None を返す。"""
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _normalize_total(q: Optional[float], v: Optional[float], t: Optional[float]) -> float:
    """
    総合スコア用：Q/V/T が None の場合は 50 点（中立）として扱い、3つの平均を返す。
    """
    def _val(x):
        return 50.0 if x is None else float(x)

    return (_val(q) + _val(v) + _val(t)) / 3.0


# ===========================================================
# 既存ヘルパー
# ===========================================================

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
    ※現状はテクニカル中心。per/pbr は未使用。
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
    # 将来 per / pbr ロジックを足す余地あり
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
    ※現状はテクニカル中心。per/pbr は未使用。
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
    # 将来 per / pbr ロジックを足す余地あり
    return score


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


# ===========================================================
# メイン：テクニカル & QVT スコア計算
# ===========================================================

def compute_indicators(
    df: pd.DataFrame,
    close_col: str,
    high_52w: float,
    low_52w: float,
    ticker: Optional[str] = None,  # 将来拡張用
    eps: Optional[float] = None,
    bps: Optional[float] = None,
    eps_fwd: Optional[float] = None,
    per_fwd: Optional[float] = None,
    roa: Optional[float] = None,
    roe: Optional[float] = None,
    equity_ratio: Optional[float] = None,      # 自己資本比率（%）
    dividend_yield: Optional[float] = None,    # 予想配当利回り（%）
):
    """
    df に各種テクニカル指標を追加し、判定に必要な値と
    Q（ビジネスの質）/ V（バリュ）/ T（タイミング）のスコアを返す。
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

    # === 順張り・逆張りスコア（元のブル／ベアスコア） ===
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

    # === 順張り/逆張りモード判定 ===
    is_trend_mode = ma75 < ma50 < ma25  # 25 > 50 > 75 なら順張りモード

    # === T スコア（タイミング）===
    # 順張り時：highprice_score を採用（割高否定スコア）
    # 逆張り時：low_score を採用（割安スコア）
    t_raw: Optional[float]
    t_max: float
    t_mode: str

    if is_trend_mode:
        t_raw = highprice_score
        t_max = 70.0   # highprice_score の理論最大値
        t_mode = "trend"
    else:
        t_raw = low_score
        t_max = 85.0   # low_score の理論最大値
        t_mode = "contrarian"

    t_score: Optional[float]
    if t_raw is None or t_max <= 0:
        t_score = None
    else:
        t_score = max(0.0, min(100.0, t_raw / t_max * 100.0))

    # === トレンド条件 / 逆張り条件（従来ロジック）===
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

    # === Q（ビジネスの質）スコア ===
    roe_score = _score_roe(roe)
    roa_score = _score_roa(roa)
    equity_score = _score_equity_ratio(equity_ratio)
    q_score = _average_scores([roe_score, roa_score, equity_score])

    # === V（バリュエーション）スコア ===
    per_score = _score_per(per)
    pbr_score = _score_pbr(pbr)
    div_score = _score_dividend_yield(dividend_yield)
    v_score = _average_scores([per_score, pbr_score, div_score])

    # === 総合 QVT スコア ===
    total_qvt_score = _normalize_total(q_score, v_score, t_score)

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
        "t_score": t_score,
        "t_mode": t_mode,  # "trend" or "contrarian"
        "trend_conditions": trend_conditions,
        "trend_comment": trend_comment,
        "contrarian_conditions": contrarian_conditions,
        "contr_comment": contr_comment,
        # ファンダメンタル
        "eps": eps,
        "bps": bps,
        "per": per,
        "pbr": pbr,
        "eps_fwd": eps_fwd,
        "per_fwd": per_fwd_calc,
        "roa": roa,
        "roe": roe,
        "equity_ratio": equity_ratio,
        "dividend_yield": dividend_yield,
        # Q / V / T スコア
        "q_score": q_score,
        "v_score": v_score,
        "total_qvt_score": total_qvt_score,
        # 内訳（UIで詳細を出したいとき用）
        "q_subscores": {
            "roe_score": roe_score,
            "roa_score": roa_score,
            "equity_ratio_score": equity_score,
        },
        "v_subscores": {
            "per_score": per_score,
            "pbr_score": pbr_score,
            "dividend_yield_score": div_score,
        },
    }
