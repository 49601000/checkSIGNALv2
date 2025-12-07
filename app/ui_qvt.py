import streamlit as st


def render_qvt_tab(tech: dict):
    """QVT（総合）タブ"""

    q = tech["q_score"]
    v = tech["v_score"]
    t = tech["t_score"]
    qvt = tech["qvt_score"]

    st.subheader("🧮 QVT（総合評価）")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Q（質）", f"{q:.1f}")
    col2.metric("V（値札）", f"{v:.1f}")
    col3.metric("T（タイミング）", f"{t:.1f}")
    col4.metric("QVT総合", f"{qvt:.1f}")

    st.markdown("---")

    if qvt >= 70:
        msg = "総合的にとても魅力的な水準（主力候補）。"
    elif qvt >= 60:
        msg = "買い検討レベル。慎重に押し目を狙いたい。"
    elif qvt >= 50:
        msg = "悪くないが他候補との比較推奨。"
    else:
        msg = "テーマ性が強くないなら見送りも選択肢。"

    st.write(msg)
