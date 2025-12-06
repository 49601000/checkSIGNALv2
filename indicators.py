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
    → T スコアの順張りモードで利用
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
    → T スコアの逆張りモードで利用
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
# タイミング用のヘルパー関数を追加
# ============================================================

def _score_timing_trend(
    highprice_score: float,
    low_score: float,
    signal_strength: int,
    price: float,
    high_52w: float,
    bb_upper1: float,
    per: Optional[float],
    pbr: Optional[float],
) -> tuple[float, str, bool]:
    """
    順張り局面用：タイミングスコア T（0〜100）とラベル、 高値掴みフラグを返す。
    """
    # 割安度（押し目度）0〜1
    low_norm = max(0.0, min(low_score / 85.0, 1.0))
    # 押し目シグナル強度（0〜3）→ 0〜1
    sig_norm = max(0.0, min(signal_strength / 3.0, 1.0))

    # ベースは「中立〜軽い押し目」あたり（50点）
    t = 50.0 + 40.0 * sig_norm + 10.0 * low_norm  # 最大でほぼ 100

    # 高値掴みリスク判定（highprice_score が低いほど危険）
    high_price_alert = False
    if highprice_score <= 40:
        high_price_alert = True
    # ついでに「52週高値付近」「BB+1σ超え」「超高PER/PBR」も危険扱いにしてもOK
    if high_52w and price >= high_52w * 0.97:
        high_price_alert = True
    if price >= bb_upper1:
        high_price_alert = True
    if per is not None and per > 35:
        high_price_alert = True
    if pbr is not None and pbr > 3.5:
        high_price_alert = True

    # 高値掴みリスクが立っているときは T を 40 点以下にキャップ
    if high_price_alert and t > 40.0:
        t = 40.0

    # ラベル付け
    if t <= 25:
        label = "高値圏（要注意）"
    elif t <= 50:
        label = "押し目シグナルなし"
    elif t <= 80:
        label = "そこそこ押し目"
    else:
        label = "バーゲン（強い押し目）"

    return t, label, high_price_alert


def _score_timing_contrarian(
    low_score: float,
    highprice_score: float,
) -> tuple[float, str, bool]:
    """
    逆張り局面用：タイミングスコア T（0〜100）とラベル、高値掴みフラグを返す。
    ※ここでは low_score（割安度）だけを見る。
    """
    # 割安度 0〜1
    low_norm = max(0.0, min(low_score / 85.0, 1.0))

    # ベース 40点（＝押し目シグナルなし）
    # そこから割安になるほど 100 点に近づく
    t = 40.0 + 60.0 * low_norm   # low_score=0 → 40, max → 100

    # highprice_score が低いときは「逆張りにすら乗りたくない高値圏」とみなしてキャップ
    high_price_alert = False
    if highprice_score <= 40:
        high_price_alert = True
    if high_price_alert and t > 40.0:
        t = 40.0

    # ラベル付け
    if t <= 25:
        label = "高値圏（要注意）"
    elif t <= 50:
        label = "押し目シグナルなし"
    elif t <= 80:
        label = "そこそこ押し目"
    else:
        label = "バーゲン（強い押し目）"

    return t, label, high_price_alert

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
#  - 順張り: highprice_score ベース
#  - 逆張り: low_score ベース
#  + 押し目シグナルとの連動
#  + 高値掴みアラートがある場合は T<=40 にキャップ
# ============================================================

def _timing_label_from_score(t_score: float) -> str:
    """
    Tスコアを言語ラベルへマッピング
    0〜30 : 高値圏（要注意）
    31〜50: 押し目シグナルなし〜様子見
    51〜80: そこそこ押し目
    81〜100: バーゲン（強い押し目）
    """
    if t_score <= 30:
        return "高値圏（要注意）"
    elif t_score <= 50:
        return "押し目シグナルなし〜様子見"
    elif t_score <= 80:
        return "そこそこ押し目"
    else:
        return "バーゲン（強い押し目）"


def _score_timing_trend(
    highprice_score: float,
    low_score: float,
    signal_strength: int,
    is_high_price_alert: bool,
) -> float:
    """
    順張りモードの T スコア
    - highprice_score をそのまま 0〜100 とみなす
    - 押し目シグナルがあれば +α
    - 高値掴みアラートがあれば T<=30 にキャップ
    """
    t_score = max(0.0, min(100.0, float(highprice_score)))

    # 押し目シグナルによるブースト（順張りは「ご褒美」扱い）
    if signal_strength >= 2:
        t_score = min(100.0, t_score + 10.0)  # そこそこ〜強い押し目
    elif signal_strength == 1:
        t_score = min(100.0, t_score + 5.0)   # 軽い押し目

    # 高値掴みアラート → どんな状況でも 30 点以上にはならない
    if is_high_price_alert:
        t_score = min(t_score, 30.0)

    return t_score


def _score_timing_contrarian(
    highprice_score: float,
    low_score: float,
    signal_strength: int,
    is_high_price_alert: bool,
) -> float:
    """
    逆張りモードの T スコア
    - low_score を 0〜100 とみなす
    - 押し目シグナルが弱いと上限をキャップ
    - 高値掴みアラートがあれば T<=40 にキャップ（安全弁）
    """
    t_score = max(0.0, min(100.0, float(low_score)))

    # 押し目シグナルとの強い連動
    if signal_strength == 0:
        # 押し目シグナルなし → どんなに条件が揃っても 40 点まで
        t_score = min(t_score, 40.0)
    elif signal_strength == 1:
        # 軽い押し目 → 70 点まで
        t_score = min(t_score, 70.0)
    # 2,3 → キャップ無し（0〜100）

    # 高値掴みアラート（基本的には逆張り局面では発生しにくいが安全弁として）
    if is_high_price_alert:
        t_score = min(t_score, 30.0)

    return t_score


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
        data_fetch.get_price_and_meta() から渡された値を利用。
      （このモジュールから外部 API は叩かない）
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

    # === 高値掴みアラート判定 ===
    high_price_alert = False
    if (
        (price >= bb_upper1)
        or (high_52w and high_52w != 0 and price >= high_52w * 0.98)
        or (rsi is not None and rsi >= 70)
    ):
        high_price_alert = True

    # === 順張り・逆張りスコア（従来のブル／ベア）===
    # === 順張り・逆張りスコア（既存） ===
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

    # === タイミングスコア T（QVT 用） ===
    if trend_conditions[0]:  # 25MA > 50MA > 75MA → 順張りモード
        t_score, timing_label, high_price_alert = _score_timing_trend(
            highprice_score=highprice_score,
            low_score=low_score,
            signal_strength=signal_strength,
            price=price,
            high_52w=high_52w,
            bb_upper1=bb_upper1,
            per=per,
            pbr=pbr,
        )
    else:
        # それ以外は逆張りモードとして扱う
        t_score, timing_label, high_price_alert = _score_timing_contrarian(
            low_score=low_score,
            highprice_score=highprice_score,
        )


    # === Q / V スコア ===
    q_score = _score_quality(roe, roa, equity_ratio)
    v_score = _score_valuation(per, pbr, dividend_yield)

    # === T スコア（モード判定＋高値掴みキャップ込み） ===
    if trend_conditions[0]:
        # 順張りモード
        t_mode = "trend"
        t_score = _score_timing_trend(
            highprice_score=highprice_score,
            low_score=low_score,
            signal_strength=signal_strength,
            is_high_price_alert=high_price_alert,
        )
    else:
        # 逆張りモード
        t_mode = "contrarian"
        t_score = _score_timing_contrarian(
            highprice_score=highprice_score,
            low_score=low_score,
            signal_strength=signal_strength,
            is_high_price_alert=high_price_alert,
        )

    timing_label = _timing_label_from_score(t_score)

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
        # --- 新しく追加したファンダスコア関連 ---
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
