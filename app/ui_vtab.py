import streamlit as st


def _fmt_ratio(x) -> str:
    """PER / PBR / 予想PER 用の表示（None 安全）"""
    if x is None:
        return "—"
    return f"{x:.2f}倍"


def _fmt_yield(x) -> str:
    """配当利回り（%）表示（None 安全）"""
    if x is None:
        return "—"
    return f"{x:.2f}%"


def render_v_tab(tech: dict):
    """V（バリュエーション）タブ UI"""

    v_score = float(tech.get("v_score", 0.0))

    per = tech.get("per")
    per_fwd = tech.get("per_fwd")
    pbr = tech.get("pbr")
    dy = tech.get("dividend_yield")

    st.subheader("💰 V（バリュエーション）")
    st.metric("Vスコア（割安度）", f"{v_score:.1f} / 100")

    st.markdown(
        f"""
- PER: **{_fmt_ratio(per)}**  
- 予想PER: **{_fmt_ratio(per_fwd)}**  
- PBR: **{_fmt_ratio(pbr)}**  
- 配当利回り: **{_fmt_yield(dy)}**
"""
    )

    st.caption(
        "PER / PBR / 配当利回りはいずれかのデータが欠損している場合「—」と表示されます。"
    )

    st.markdown("---")
    st.caption(
        "Vスコアは PER / PBR / 配当利回りを正規化したざっくり指標。"
        "セクター特性とセットで見るのが推奨。"
    )
