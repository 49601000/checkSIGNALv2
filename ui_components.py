import streamlit as st

from data_fetch import convert_ticker, get_price_and_meta
from indicators import compute_indicators


def setup_page():
    st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
    st.title("🔍買いシグナルチェッカー")


def render_app():
    setup_page()

    # ------------ Alpha Vantage API Key の存在チェック ------------
    # .streamlit/secrets.toml に
    # ALPHA_VANTAGE_API_KEY = "xxxxx"
    # を設定しておくこと
    if "ALPHA_VANTAGE_API_KEY" not in st.secrets:
        st.error("ALPHA_VANTAGE_API_KEY が st.secrets に設定されていません。")
        st.stop()

    # デバッグ用：APIキーが読めているか（不要ならコメントアウト）
    # st.write(
    #     "ALPHA_VANTAGE_API_KEY loaded?:",
    #     "ALPHA_VANTAGE_API_KEY" in st.secrets,
    # )

    # ------------ 入力 ------------
    user_input = st.text_input("ティッカーを入力（例：7203, 8306.T, AAPL）", value="")
    ticker = convert_ticker(user_input)

    if not ticker:
        st.stop()

    # ------------ データ取得 ------------
    try:
        # 日本株 → IRBANK / yfinance
        # 米国株 → Alpha Vantage / yfinance（data_fetch 側で判定）
        base = get_price_and_meta(ticker)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    df = base["df"]
    close_col = base["close_col"]
    close = base["close"]
    previous_close = base["previous_close"]
    high_52w = base["high_52w"]
    low_52w = base["low_52w"]
    company_name = base["company_name"]
    dividend_yield = base["dividend_yield"]

    # ファンダ系
    eps = base.get("eps")             # 実績 EPS
    bps = base.get("bps")             # 実績 BPS
    eps_fwd = base.get("eps_fwd")     # 予想 EPS（あれば）
    per_fwd = base.get("per_fwd")     # 予想 PER（あれば）

    roe = base.get("roe")             # ROE（%）
    roa = base.get("roa")             # ROA（%）
    equity_ratio = base.get("equity_ratio")  # 自己資本比率（%）

    # ------------ テクニカル + QVT スコア計算 ------------
    try:
        tech = compute_indicators(
            df,
            close_col,
            high_52w,
            low_52w,
            eps=eps,
            bps=bps,
            eps_fwd=eps_fwd,
            per_fwd=per_fwd,
            roe=roe,
            roa=roa,
            equity_ratio=equity_ratio,
            dividend_yield=dividend_yield,
        )
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # ------------ 価格の色 ------------
    if close > previous_close:
        price_color = "red"
    elif close < previous_close:
        price_color = "green"
    else:
        price_color = "black"

    # ------------ ヘッダー部分（現在価格 + PER/PBR + MA）------------
    st.markdown("---")
    st.markdown(f"## 📌 {ticker}（{company_name}）")

    # PER / PBR の文字列整形（None のときは "—"）
    per_val = tech.get("per")
    pbr_val = tech.get("pbr")
    per_str = f"{per_val:.2f}倍" if per_val is not None else "—"
    pbr_str = f"{pbr_val:.2f}倍" if pbr_val is not None else "—"

    # 予想 PER（compute_indicators 側で per_fwd を計算済み）
    per_fwd_val = tech.get("per_fwd")
    per_fwd_str = f"{per_fwd_val:.2f}倍" if per_fwd_val is not None else "—"

    html_header = (
        f"**現在価格**: "
        f"<span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span>  <br>"
        f"（前日終値: {previous_close:.2f}）  <br><br>"
        f"**PER**: {per_str} ｜ **PBR**: {pbr_str}  <br><br>"
        f"**25MA**: {tech['ma25']:.2f} {tech['arrow25']} ｜ "
        f"**50MA**: {tech['ma50']:.2f} {tech['arrow50']} ｜ "
        f"**75MA**: {tech['ma75']:.2f} {tech['arrow75']}"
    )
    st.markdown(html_header, unsafe_allow_html=True)

    # ------------ RSI / BB ------------
    st.markdown(
        f"""
**RSI**: {tech["rsi"]:.1f} ｜ **BB判定**: {tech["bb_icon"]} {tech["bb_text"]}
        """
    )

    # 高値掴みアラート
    if tech.get("high_price_alert"):
        st.warning("⚠️ 高値掴みリスク（高値圏に近い水準です）")

    # 配当利回り（取れているときだけ）
    if dividend_yield is not None:
        st.markdown(f"**予想配当利回り（過去1年ベース）**: {dividend_yield:.2f}%")

    # 押し目シグナル
    st.markdown(f"### {tech['signal_icon']} {tech['signal_text']}")
    st.progress(tech["signal_strength"] / 3)

    # ================================
    # 🔷 Q / V / T / QVT セクション
    # ================================
    st.markdown("---")
    st.markdown("### 🧩 QVTスコア（質×値札×タイミング）")

    q_score = tech.get("q_score", 0.0)
    v_score = tech.get("v_score", 0.0)
    t_score = tech.get("t_score", 0.0)
    qvt_score = tech.get("qvt_score", 0.0)
    timing_label = tech.get("timing_label", "")

    col_q, col_v, col_t, col_total = st.columns(4)

    with col_q:
        st.metric("Q（ビジネスの質）", f"{q_score:.1f} / 100")
        st.caption(
            f"ROE: {roe:.1f}%｜ROA: {roa:.1f}%｜自己資本比率: {equity_ratio:.1f}%"
            if (roe is not None and roa is not None and equity_ratio is not None)
            else "ROE / ROA / 自己資本比率の一部または全部が取得できていません"
        )

    with col_v:
        st.metric("V（バリュエーション）", f"{v_score:.1f} / 100")
        st.caption(
            f"PER: {per_str}｜PBR: {pbr_str}｜利回り: "
            + (f"{dividend_yield:.2f}%" if dividend_yield is not None else "—")
        )

    with col_t:
        st.metric("T（タイミング）", f"{t_score:.1f} / 100")
        st.caption(f"タイミング評価: {timing_label}")

    with col_total:
        st.metric("QVT総合スコア", f"{qvt_score:.1f} / 100")
        st.caption("Q・V・T の単純平均")

    # ================================
    # 📈 裁量買いレンジ（既存ロジック）
    # ================================
    st.markdown("---")

    # 順張り（25 > 50 > 75）
    if tech["trend_conditions"][0]:
        center_price = (tech["ma25"] + tech["ma50"]) / 2
        upper_price = center_price * 1.03
        lower_price = max(center_price * 0.95, tech["bb_lower1"])

        st.markdown("### 📈 ＜順張り＞裁量買いレンジ")

        st.markdown(
            f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 25MA ＞ 50MA ＞ 75MA | {"○" if tech["trend_conditions"][0] else "×"} |
| 短期傾向 | MA25 が横ばい〜緩やか上昇 | {"○" if tech["trend_conditions"][1] else "×"} |
| 割高否定 | ブルスコア（高値否定スコア） | {tech["highprice_score"]:.1f} |
| 中心価格 | 25MA と 50MA の平均 | {center_price:.2f} |
| 上側許容 | ×1.03 | {upper_price:.2f} |
| 下側許容 | ×0.95 または BB-1σ | {lower_price:.2f} |
| 判定 | — | **{tech["trend_comment"]}** |
"""
        )
    # 逆張り（下降 or 横ばい）
    else:
        center_price = (tech["ma25"] + tech["bb_lower1"]) / 2
        upper_price = center_price * 1.08
        lower_price = center_price * 0.97

        st.markdown("### 🧮 ＜逆張り＞裁量買いレンジ")

        st.markdown(
            f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 下降 or 横ばい | {"○" if tech["contrarian_conditions"][0] else "×"} |
| 短期傾向 | MA25 が下降 | {"○" if tech["contrarian_conditions"][1] else "×"} |
| 割安判定 | ベアスコア（割安スコア） | {tech["low_score"]:.1f} |
| 中心価格 | 25MA と BB−1σ の平均 | {center_price:.2f} |
| 上側許容 | ×1.08 | {upper_price:.2f} |
| 下側許容 | ×0.97 | {lower_price:.2f} |
| 判定 | — | **{tech["contr_comment"]}** |
"""
        )
