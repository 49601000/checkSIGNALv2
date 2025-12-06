# ui_components.py
import streamlit as st

from data_fetch import convert_ticker, get_price_and_meta
from indicators import compute_indicators


def setup_page():
    st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
    st.title("🔍買いシグナルチェッカー")


def render_app():
    setup_page()

    # ------------ Alpha Vantage API Key の存在チェック ------------
    if "ALPHA_VANTAGE_API_KEY" not in st.secrets:
        st.error("ALPHA_VANTAGE_API_KEY が st.secrets に設定されていません。")
        st.stop()

    # ------------ 入力 ------------
    user_input = st.text_input("ティッカーを入力（例：7203, 8306.T, AAPL）", value="")
    ticker = convert_ticker(user_input)

    if not ticker:
        st.stop()

    # ------------ データ取得 ------------
    try:
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
    eps = base.get("eps")
    bps = base.get("bps")
    eps_fwd = base.get("eps_fwd")
    per_fwd = base.get("per_fwd")

    # Q 用のファンダ
    roe = base.get("roe")
    roa = base.get("roa")
    equity_ratio = base.get("equity_ratio")

    # ------------ テクニカル指標 + PER/PBR + Q/V/T ------------
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

    # PER / PBR の文字列整形（None のときは "—"）
    per_val = tech.get("per")
    pbr_val = tech.get("pbr")
    per_str = f"{per_val:.2f}倍" if per_val is not None else "—"
    pbr_str = f"{pbr_val:.2f}倍" if pbr_val is not None else "—"

    # -------------------------------
    # ① ヘッダー
    # -------------------------------
    st.markdown("---")
    st.markdown(f"## 📌 {ticker}（{company_name}）")
    st.markdown(
        f"""
**現在価格**: <span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span>  
（前日終値: {previous_close:.2f}）  

**PER**: {per_str} ｜ **PBR**: {pbr_str}
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------
    # ② 総合 QVT スコア
    # -------------------------------
    q_score = tech["q_score"]
    v_score = tech["v_score"]
    t_score = tech["t_score"]
    qvt_total = tech["qvt_total"]

    st.markdown("### 🎯 総合 QVT スコア")

    st.metric("総合スコア (Q+V+T)", f"{qvt_total:.1f} / 100")

    col_q, col_v, col_t = st.columns(3)
    col_q.metric("Q: ビジネスの質", f"{q_score:.1f} / 100")
    col_v.metric("V: バリュエーション", f"{v_score:.1f} / 100")
    col_t.metric("T: タイミング", f"{t_score:.1f} / 100")

    # -------------------------------
    # ③ Q: ビジネスの質
    # -------------------------------
    st.markdown("---")
    st.markdown("### 🧱 Q: ビジネスの質（ROE / ROA / 自己資本比率）")

    q_roe = tech.get("roe")
    q_roa = tech.get("roa")
    q_eq = tech.get("equity_ratio")

    q_roe_str = f"{q_roe:.1f}%" if q_roe is not None else "—"
    q_roa_str = f"{q_roa:.1f}%" if q_roa is not None else "—"
    q_eq_str = f"{q_eq:.1f}%" if q_eq is not None else "—"

    st.markdown(
        f"""
| 指標 | 数値 | 補足 |
|---|---|---|
| ROE | {q_roe_str} | 株主資本に対する利益率 |
| ROA | {q_roa_str} | 総資産に対する利益率 |
| 自己資本比率 | {q_eq_str} | 財務の健全性 |
| **Qスコア** | **{q_score:.1f} / 100** |  |
"""
    )

    # -------------------------------
    # ④ V: バリュエーション
    # -------------------------------
    st.markdown("---")
    st.markdown("### 💰 V: バリュエーション（値札の妥当性）")

    div_yield = tech.get("dividend_yield")

    div_str = f"{div_yield:.2f}%" if div_yield is not None else "—"

    st.markdown(
        f"""
| 指標 | 数値 | 補足 |
|---|---|---|
| PER | {per_str} | 利益に対する株価の倍率 |
| PBR | {pbr_str} | 純資産に対する株価の倍率 |
| 予想配当利回り | {div_str} | 過去1年配当から算出 |
| **Vスコア** | **{v_score:.1f} / 100** |  |
"""
    )

    # -------------------------------
    # ⑤ T: タイミング & テクニカル
    # -------------------------------
    st.markdown("---")
    st.markdown("### 📈 T: タイミング（テクニカル状況）")

    st.markdown(
        f"""
**25MA**: {tech['ma25']:.2f} {tech['arrow25']} ｜ 
**50MA**: {tech['ma50']:.2f} {tech['arrow50']} ｜ 
**75MA**: {tech['ma75']:.2f} {tech['arrow75']}  
**RSI**: {tech["rsi"]:.1f} ｜ **BB判定**: {tech["bb_icon"]} {tech["bb_text"]}  
        """
    )

    t_mode = tech.get("t_mode", "trend")
    mode_label = "順張りモード" if t_mode == "trend" else "逆張りモード"

    st.markdown(
        f"**タイミングスコア (T)**: **{t_score:.1f} / 100** （{mode_label}）"
    )

    # 押し目シグナル
    st.markdown(f"#### {tech['signal_icon']} {tech['signal_text']}")
    st.progress(tech["signal_strength"] / 3)

    # ------------ 裁量買いレンジ（順張り or 逆張り）------------
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
| 割高否定 | ブルスコア（highprice） | {tech["highprice_score"]:.1f} |
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
| 割安判定 | ベアスコア（low_score） | {tech["low_score"]:.1f} |
| 中心価格 | 25MA と BB−1σ の平均 | {center_price:.2f} |
| 上側許容 | ×1.08 | {upper_price:.2f} |
| 下側許容 | ×0.97 | {lower_price:.2f} |
| 判定 | — | **{tech["contr_comment"]}** |
"""
        )
