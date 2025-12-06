# ui_components.py
import streamlit as st

from data_fetch import convert_ticker, get_price_and_meta
from indicators import compute_indicators


def setup_page():
    st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
    st.title("🔍買いシグナルチェッカー")


def render_app():
    setup_page()

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

    # ------------ テクニカル指標 ------------
    try:
        tech = compute_indicators(df, close_col, high_52w, low_52w)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # ------------ 価格色 ------------
    if close > previous_close:
        price_color = "red"
    elif close < previous_close:
        price_color = "green"
    else:
        price_color = "black"

    # ------------ Part2: UI 表示 ------------
    st.markdown("---")
    st.markdown(f"## 📌 {ticker}（{company_name}）")

    # PER / PBR 表示用の文字列
    per_str = "—"
    pbr_str = "—"
    if tech["per"] is not None:
        per_str = f"{tech['per']:.2f}倍"
    if tech["pbr"] is not None:
        pbr_str = f"{tech['pbr']:.2f}倍"

    st.markdown(
        f"""
**現在価格**: <span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span>  
（前日終値: {previous_close:.2f}）  

**PER**: {per_str} ｜ **PBR**: {pbr_str}  

**25MA**: {tech["ma25"]:.2f} {tech["arrow25"]} ｜ **50MA**: {tech["ma50"]:.2f} {tech["arrow50"]} ｜ **75MA**: {tech["ma75"]:.2f} {tech["arrow75"]}
        """,
        unsafe_allow_html=True,
    )


**25MA**: {tech["ma25"]:.2f} {tech["arrow25"]} ｜ **50MA**: {tech["ma50"]:.2f} {tech["arrow50"]} ｜ **75MA**: {tech["ma75"]:.2f} {tech["arrow75"]}
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
**RSI**: {tech["rsi"]:.1f} ｜ **BB判定**: {tech["bb_icon"]} {tech["bb_text"]}
        """
    )

    if dividend_yield is not None:
        st.markdown(f"**予想配当利回り（過去1年ベース）**: {dividend_yield:.2f}%")

    st.markdown(f"### {tech['signal_icon']} {tech['signal_text']}")
    st.progress(tech["signal_strength"] / 3)

    # ------------ Part3: 順張り or 逆張りレンジ ------------
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
| 割高否定 | ブルスコアが60点以上で「押し目」と判定（ブルスコアは RSI・PER・PBR・BB・52週高値の95%未満などを加点評価／スコアが高いほど割高否定傾向） | {tech["highprice_score"]} |
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
| 割安判定 | ベアスコアが60点以上で「割安」と判定（RSI・PER・PBR・BB・52週安値などを加点評価／スコアが高いほど割安傾向） | {tech["low_score"]} |
| 中心価格 | 25MA と BB−1σ の平均 | {center_price:.2f} |
| 上側許容 | ×1.08 | {upper_price:.2f} |
| 下側許容 | ×0.97 | {lower_price:.2f} |
| 判定 | — | **{tech["contr_comment"]}** |
"""
        )
