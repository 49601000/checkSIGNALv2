import streamlit as st
from modules.q_correction import apply_q_correction


def render_q_tab(tech: dict):
    """Q（ビジネスの質）タブ + 補正UI"""

    q_score = tech["q_score"]
    v_score = tech["v_score"]
    t_score = tech["t_score"]

    roe = tech.get("roe")
    roa = tech.get("roa")
    equity_ratio = tech.get("equity_ratio")

    st.subheader("🏢 Q（ビジネスの質）")

    # ------------------------------
    # 生のQスコア
    # ------------------------------
    st.metric("Qスコア（元）", f"{q_score:.1f} / 100")

    st.markdown("#### 財務・収益性（元データ）")

    st.markdown(
        f"""
- ROE: **{roe:.1f}%**  
- ROA: **{roa:.1f}%**  
- 自己資本比率: **{equity_ratio:.1f}%**
"""
    )

    st.markdown("---")
    st.markdown("### 🧩 セクター平均を入力して Qスコアを補正")

    col1, col2 = st.columns(2)

    with col1:
        sector_roe = st.number_input(
            "セクター平均ROE（%）",
            min_value=0.0, max_value=40.0, value=10.0, step=0.1
        )

    with col2:
        sector_roa = st.number_input(
            "セクター平均ROA（%）",
            min_value=0.0, max_value=20.0, value=4.0, step=0.1
        )

    # 補正ボタン
    correct_button = st.button("補正する")

    if correct_button:
        result = apply_q_correction(
            original_q=q_score,
            v_score=v_score,
            t_score=t_score,
            roe=roe,
            roa=roa,
            equity_ratio=equity_ratio,
            sector_roe=sector_roe,
            sector_roa=sector_roa,
        )

        q_corr = result["q_corrected"]
        qvt_corr = result["qvt_corrected"]

        if q_corr is None:
            st.error("補正計算ができません（データ不足）。")
            return

        st.markdown("### 📌 補正後スコア")

        c1, c2 = st.columns(2)

        with c1:
            st.metric("Qスコア（補正後）", f"{q_corr:.1f}")

        with c2:
            st.metric("QVT（補正後）", f"{qvt_corr:.1f}")

        st.info("セクター基準を用いて Q と QVT を補正した結果を表示しています。")

    st.markdown("---")

    st.caption(
        "Q補正は、ROE / ROA をセクター平均と比較したバイアスを付与する簡易モデルです。"
    )
