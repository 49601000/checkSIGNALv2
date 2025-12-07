"""
q_correction.py
----------------

【目的】
本モジュールは、既存の Q スコア（ROE・ROA・自己資本比率に基づく
ビジネスの質評価）に対して、
「セクター特性を加味した補正バイアス」を適用するための補助モジュールである。

既存の Q スコアは、個別企業の絶対的な財務指標に基づいて 0〜100 に正規化される。
しかし、企業が属するセクターの構造的収益性（例：鉄道・インフラは低ROEが普通、
ソフトウェア・半導体は高ROEが普通）を加味しないと、
“本来の平均値”からの乖離を適切に評価できないケースが生じる。

本モジュールの役割は、
    ● 既存 Q スコアを作り直すのではなく  
    ● セクターに対する相対位置をバイアスとして付与し  
    ● 「補正後Q」として投資家の判断材料を拡張する  
という点にある。

【基本思想】
- セクター平均 ROE / ROA を 100 としたときの偏差（±）を計算する
- その偏差を最大 ±20pt の範囲でクリップし、既存 Q スコアに加算する
- 補正後 Q は 0〜100 にクリップして返す
- 補正後 QVT スコアも合わせて再計算する
- 自己資本比率（Equity Ratio）はセクター間差の評価が難しいため補正に使用しない
  （元のQスコア内の絶対評価に委譲する）

【この方式を採用する理由】
- 元の Q スコアの構造や意味を壊さずに “上書き補正” できる
- スコア全体の整合性（Q / V / T の比較可能性）が保たれる
- ユーザーが「補正前 / 補正後」を並べて見た時に直感的に理解しやすい
- 自動計算ではなく「必要な時だけ手動補正」という運用思想に合致する

【注意事項】
- セクター平均値はユーザー入力に依存するため、補正はあくまで裁量ベース
- ROE / ROA のいずれか、またはセクター値が欠損する場合は補正を行わない
- 今後、別方式（絶対評価型Qの作り直し）を追加する場合にも拡張しやすい構成

このモジュールは Q スコアの“代替”ではなく、“補助レイヤー”として設計されている。
"""

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
