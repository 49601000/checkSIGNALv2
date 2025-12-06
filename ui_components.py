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
    eps = base["eps"]
    bps = base["bps"]

    # ------------ テクニカル指標 + PER/PBR ------------
    try:
        tech = compute_indicators(
            df,
            close_col,
            high_52w,
            low_52w,
            eps=eps,
            bps=bps,
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
    per_str = "—"
    pbr_str = "—"
    if tech["per"] is not None:
        per_str = f"{tech['per']:.2f}倍"
    if tech["pbr"] is not None:
        pbr_str = f"{tech['pbr']:.2f}倍"

    price_text = f"{close:.2f}"
    prev_text = f"{previous_close:.2f}"
    ma25_text = f"{tech['ma25']:.2f} {tech['arrow25']}"
    ma50_text = f"{tech['ma50']:.2f} {tech['arrow50']}"
    ma75_text = f"{tech['ma75']:.2f} {tech['arrow75']}"

    # 複雑な f"""...""" をやめて、1行の文字列を連結して安全に生成
    html_header = (
        f"**現在価格**: "
        f"<span style='color:{price_color}; font-weight:bold;'>{price_text}</span>  <br>"
        f"（前日終値: {prev_text}）  <br><br>"
        f"**PER**: {per_str} ｜ **PBR**: {pbr_str}  <br><br>"
        f"**25MA**: {ma25_text} ｜ **50MA**: {ma50_text} ｜ **75MA**: {ma75_text}"
    )
    st.markdown(html_header, unsafe_allow_html=True)

    # ------------ RSI / BB ------------
    st.markdown(
        f"""
**RSI**: {tech["rsi"]:.1f} ｜ **BB判定**: {tech["bb_icon"]} {tech["bb_text"]}
        """
    )

    # 配当利回り（取れているときだけ）
    if dividend_yield is not None:
        st.markdown(f"**予想配当利回り（過去1年ベース）**: {dividend_yield:.2f}%")

    # 押し目シグナル
    st.markdown(f"### {tech['signal_icon']} {tech['signal_text']}")
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
| 割高否定 | ブルスコアが60点以上で「押し目」と判定 | {tech["highprice_score"]} |
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
| 割安判定 | ベアスコアが60点以上で「割安」と判定 | {tech["low_score"]} |
| 中心価格 | 25MA と BB−1σ の平均 | {center_price:.2f} |
| 上側許容 | ×1.08 | {upper_price:.2f} |
| 下側許容 | ×0.97 | {lower_price:.2f} |
| 判定 | — | **{tech["contr_comment"]}** |
"""
        )
