import streamlit as st


def render_v_tab(tech: dict):
    """V（バリュエーション）タブUI"""

    v_score = tech["v_score"]
    per = tech.get("per")
    pbr = tech.get("pbr")
    per_fwd = tech.get("per_fwd")
    dy = tech.get("dividend_yield")

    st.subheader("💰 V（バリュエーション）")
    st.metric("Vスコア", f"{v_score:.1f} / 100")

    st.markdown("#### 主な指標")

    st.markdown(
        f"""
- PER: **{per:.2f}倍**  
- 予想PER: **{per_fwd:.2f}倍**  
- PBR: **{pbr:.2f}倍**  
- 配当利回り: **{(dy or 0):.2f}%**
        """
    )

    st.markdown("---")
    st.caption(
        "Vスコアは PER / PBR / 配当利回りを正規化したざっくり指標。"
        "セクター特性とセットで見るのが推奨。"
    )
