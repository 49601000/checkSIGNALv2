import streamlit as st


def render_qvt_tab(tech: dict):
    """QVT（総合）タブ"""

    # 元スコア
    q = float(tech["q_score"])
    v = float(tech["v_score"])
    t = float(tech["t_score"])
    qvt = float(tech["qvt_score"])

    # 🔽 Qタブでの補正結果（あれば）を取得
    corr = st.session_state.get("q_correction_result")

    if corr:
        q_corr = float(corr.get("q_corrected", q))
        qvt_corr = float(corr.get("qvt_corrected", qvt))
    else:
        q_corr = q
        qvt_corr = qvt

    st.subheader("🧮 QVT（総合評価）")

    col1, col2, col3, col4 = st.columns(4)
    # Q は補正後を表示（delta で差分を見せてもいい）
    if corr:
        col1.metric("Q（質）", f"{q_corr:.1f}", delta=f"{q_corr - q:+.1f}")
        col4.metric("QVT総合", f"{qvt_corr:.1f}", delta=f"{qvt_corr - qvt:+.1f}")
    else:
        col1.metric("Q（質）", f"{q:.1f}")
        col4.metric("QVT総合", f"{qvt:.1f}")

    col2.metric("V（値札）", f"{v:.1f}")
    col3.metric("T（タイミング）", f"{t:.1f}")

    st.markdown("---")

    # 🔽 メッセージ判定は「補正後QVT」があればそちらを使う
    qvt_for_msg = qvt_corr if corr else qvt

    if qvt_for_msg >= 70:
        msg = "総合的にとても魅力的な水準（主力候補）。"
    elif qvt_for_msg >= 60:
        msg = "買い検討レベル。慎重に押し目を狙いたい。"
    elif qvt_for_msg >= 50:
        msg = "悪くないが他候補との比較推奨。"
    else:
        msg = "テーマ性が強くないなら見送りも選択肢。"

    st.write(msg)

    if corr:
        st.caption("※ コメントは補正後QVTスコアをもとに判定しています。")
