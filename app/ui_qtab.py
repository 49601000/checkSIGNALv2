import streamlit as st
from modules.q_correction import apply_q_correction


def _fmt_pct(x) -> str:
    """None 対応付きの % 表示用ヘルパー"""
    if x is None:
        return "—"
    return f"{x:.1f}%"


def render_q_tab(tech: dict):
    """Q（ビジネスの質）タブ + 補正UI"""

    q_score = float(tech.get("q_score", 0.0))
    v_score = float(tech.get("v_score", 0.0))
    t_score = float(tech.get("t_score", 0.0))

    roe = tech.get("roe")
    roa = tech.get("roa")
    equity_ratio = tech.get("equity_ratio")

    st.subheader("🏢 Q（ビジネスの質）")

    # ------------------------------
    # 生のQスコア
    # ------------------------------
    st.metric("Qスコア（元）", f"{q_score:.1f} / 100")

    st.markdown("#### 財務・収益性（元データ）")

    if roe is None and roa is None and equity_ratio is None:
        st.caption("ROE / ROA / 自己資本比率のデータが取得できませんでした。")
    else:
        st.markdown(
            f"""
- ROE: **{_fmt_pct(roe)}**  
- ROA: **{_fmt_pct(roa)}**  
- 自己資本比率: **{_fmt_pct(equity_ratio)}**
"""
        )

    st.markdown("---")
    st.markdown("### 🧩 セクター平均を入力して Qスコアを補正")

    col1, col2 = st.columns(2)

    with col1:
        sector_roe = st.number_input(
            "セクター平均ROE（%）",
            min_value=0.0,
            max_value=40.0,
            value=10.0,
            step=0.1,
        )

    with col2:
        sector_roa = st.number_input(
            "セクター平均ROA（%）",
            min_value=0.0,
            max_value=20.0,
            value=4.0,
            step=0.1,
        )

    # 補正ボタン
    if st.button("補正する"):

        # ROE/ROA が取れていなければここで止める
        if roe is None or roa is None:
            st.error("ROE / ROA のデータが不足しているため補正計算ができません。")
            return

        result = apply_q_correction(
            tech=tech,
            sector_roe=sector_roe,
            sector_roa=sector_roa,
        )

        q_corr = result.get("q_corrected")
        qvt_corr = result.get("qvt_corrected")

        if q_corr is None or qvt_corr is None:
            st.error("補正計算ができません（データ不足または計算エラー）。")
            return

        # 🔽 ここから表示
        st.markdown("### 📌 補正結果")

        c1, c2 = st.columns(2)

        with c1:
            st.metric("Qスコア（補正前）", f"{q_score:.1f}")

        with c2:
            st.metric("Qスコア（補正後）", f"{q_corr:.1f}")

        # ✅ QVTタブ用に session_state に保存
        st.session_state["q_correction_result"] = {
            "q_base": q_score,
            "q_corrected": q_corr,
            "qvt_corrected": qvt_corr,
        }

        # 説明文
        st.info("セクター基準を用いて Q を補正した結果を表示しています。")
        st.caption(
            "Q補正は、ROE / ROA をセクター平均と比較したバイアスを付与する簡易モデルです。"
        )

    # ここより下には何も置かない（常時表示したくないため）
