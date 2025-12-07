import streamlit as st


def render_t_tab(tech: dict):
    """T（タイミング）タブUI"""

    t_score = tech["t_score"]
    timing_label = tech["timing_label"]
    qvt_score = tech["qvt_score"]

    st.subheader("⏰ T（タイミング）")
    st.metric("Tスコア（タイミング）", f"{t_score:.1f} / 100")

    st.markdown(
        f"""
        <div style="font-size:1.2rem; color:#0066cc; font-weight:bold;">
            タイミング評価: {timing_label}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### 📌 裁量買いレンジ（目安）")

    trend_conditions = tech["trend_conditions"]
    contrarian_conditions = tech["contrarian_conditions"]

    is_trend_mode = tech["t_mode"] == "trend"

    # -------------------------
    # 順張りモード
    # -------------------------
    if is_trend_mode:
        mode_label = "📈 順張り（上昇トレンド押し目狙い）"

        mid_trend_ok = "○" if trend_conditions[0] else "×"
        short_trend_ok = "○" if trend_conditions[1] else "×"
        qvt_ok = "○" if qvt_score >= 60 else "×"

        # ★ dict に合わせてキー名を修正
        center_price = (tech["ma_25"] + tech["ma_50"]) / 2
        upper_price = center_price * 1.03
        lower_price = max(center_price * 0.95, tech["bb_minus1"])

        comment_text = tech["trend_comment"]

        mid_trend_text = "25MA ＞ 50MA ＞ 75MA"
        short_trend_text = "MA25 横ばい〜緩やか上昇"

    # -------------------------
    # 逆張りモード
    # -------------------------
    else:
        mode_label = "🧮 逆張り（調整局面の押し目狙い）"

        mid_trend_ok = "○" if contrarian_conditions[0] else "×"
        short_trend_ok = "○" if contrarian_conditions[1] else "×"
        qvt_ok = "○" if qvt_score >= 60 else "×"

        # ★ こちらも同様にキー名を揃える
        center_price = (tech["ma_25"] + tech["bb_minus1"]) / 2
        upper_price = center_price * 1.08
        lower_price = center_price * 0.97

        comment_text = tech["contr_comment"]

        mid_trend_text = "下降 or 横ばい（or MA接近）"
        short_trend_text = "MA25 下降"

    # 表示
    st.markdown(f"**モード**: {mode_label}")

    st.markdown(
        f"""
    | 項目 | 内容 | 判定 |
    |---|---|:---:|
    | 中期トレンド | {mid_trend_text} | {mid_trend_ok} |
    | 短期傾向 | {short_trend_text} | {short_trend_ok} |
    | 総合力 | QVTスコア ≧ 60 | {qvt_ok} |
        """
    )

    st.markdown(
        f"""
        <div style="font-size:1.1rem; color:#0066cc; font-weight:bold; margin-top:0.5rem;">
            コメント: {comment_text}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
中心価格（目安）: **{center_price:.2f}**  
買い検討レンジ（目安）: **{lower_price:.2f} 〜 {upper_price:.2f}**
"""
    )

    st.info(
        "※ 裁量買いレンジは環境チェック・トレンド・QVTスコアを組み合わせた“参考値”です。"
    )
