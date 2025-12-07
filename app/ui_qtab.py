import streamlit as st


def render_q_tab(tech: dict):
    """Q（ビジネスの質）タブUI"""

    q_score = tech["q_score"]
    roe = tech.get("roe")
    roa = tech.get("roa")
    equity_ratio = tech.get("equity_ratio")

    st.subheader("🏢 Q（ビジネスの質）")
    st.metric("Qスコア", f"{q_score:.1f} / 100")

    # --------------------------
    # 生の財務指標
    # --------------------------
    st.markdown("#### 財務・収益性の概要")

    if roe is not None:
        st.markdown(f"- ROE: **{roe:.1f}%**")
    if roa is not None:
        st.markdown(f"- ROA: **{roa:.1f}%**")
    if equity_ratio is not None:
        st.markdown(f"- 自己資本比率: **{equity_ratio:.1f}%**")

    if roe is None and roa is None and equity_ratio is None:
        st.caption("ROE/ROA/自己資本比率が取得できていません。")

    st.markdown("---")
    st.markdown("### Q指標の一般的な読み方")

    st.markdown(
        """
- **ROE**：株主資本をどれだけ効率よく増やしているか  
- **ROA**：会社が持つ総資産をどれだけ効率的に使えるか  
- **自己資本比率**：財務の健全性

セクターごとに基準が異なるため、あくまで“質のざっくり指標”として使う。
"""
    )

    st.markdown("---")
