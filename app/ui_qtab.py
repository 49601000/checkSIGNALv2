import streamlit as st
from modules.q_correction import apply_q_correction


def _fmt_pct(x) -> str:
    """None 対応付きの % 表示用ヘルパー"""
    if x is None:
        return "—"
    return f"{x:.1f}%"


def render_q_tab(tech: dict):
    """Q（ビジネスの質）タブ + 補正UI + 解説"""

    q_score = float(tech.get("q_score", 0.0))
    # v_score / t_score はここでは使わないが、将来拡張用に残すならコメントアウトでもOK
    # v_score = float(tech.get("v_score", 0.0))
    # t_score = float(tech.get("t_score", 0.0))

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

        # 🔽 補正結果表示（Qだけ）
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

    # ==============================
    # ここから下は常時表示の「Q解説」
    # ==============================
    st.markdown("---")
    st.markdown("### 📚 Qスコアの見方（ざっくりガイド）")

    # ─ ① 指標そのものの意味 ─
    st.markdown("#### ① 指標そのものの意味")

    st.markdown(
        """
- **ROE（自己資本利益率）**  
  - 株主が出したお金（自己資本）をどれだけ効率よく増やしているか。  
  - **ざっくり目安**：  
    - 10% 前後 … 「標準〜やや優秀」  
    - 15% 以上 … 「かなり高収益」  
  - ただし、自己資本比率が低いのに ROE だけ高い場合は、**借入レバレッジで盛っている可能性**もある。

- **ROA（総資産利益率）**  
  - 会社が持っている総資産（現金・設備・不動産・投資など）をどれだけ利益に変えられているか。  
  - **ざっくり目安**：  
    - 3〜5% … 「標準」  
    - 5〜8%以上 … 「かなり効率的」  
  - ROA がしっかり高いほど、「資産の使い方がうまいビジネス」。

- **自己資本比率**  
  - 総資産のうち、どれだけを**自前の資本**で賄っているか（≒どれだけ借金に依存していないか）。  
  - **ざっくり目安**：  
    - 30% 未満 … 攻め気味・レバレッジ高め（景気悪化局面では注意）  
    - 40〜50% … 標準〜やや健全  
    - 60%以上 … かなり堅い財務体質（そのぶん成長投資は控えめなケースも）
"""
    )

    st.markdown("---")

    # ─ ② セクターごとのざっくり目安 ─
    st.markdown("#### ② セクターごとのざっくり目安")

    st.markdown(
        """
※あくまで「ざっくりした感覚値」です。個別銘柄や国ごとにかなりブレがあります。

| セクターの例 | ROE の目安 | ROA の目安 | 自己資本比率の目安 |
|---|---|---|---|
| 生活必需品・インフラ（食品・日用品・鉄道・電力・通信など） | 8〜12% | 3〜6% | 40〜60%以上 |
| 成長株・テック（ソフトウェア・半導体・ネットサービスなど） | 10〜20%以上 | 5〜10% | 30〜50%（やや低めでも許容） |
| 景気敏感（自動車・機械・素材など） | 8〜12% | 3〜6% | 30〜50% |
| 資本集約（不動産・商社・重工・プラントなど） | 6〜10% | 2〜5% | 30〜50% |
| 金融（銀行・保険・証券など） | 8〜12% | 0.5〜2% | 規制上の自己資本比率を見る（単純比較は不可） |
"""
    )

    st.markdown("---")

    # ─ ③ 組み合わせでどう読むかの具体例 ─
    st.markdown("#### ③ 組み合わせでどう読むかの例")

    st.markdown(
        """
- **例A：ROE 15% / ROA 7% / 自己資本比率 60%**  
  → 高収益かつ資産効率も高く、財務も堅い。  
  → **「攻守バランスの良い高品質ビジネス」** と評価しやすい。

- **例B：ROE 15% / ROA 3% / 自己資本比率 20%**  
  → ROE は高いが、ROA は平凡で自己資本比率が低い。  
  → 借入レバレッジで ROE を稼いでいる可能性が高く、**景気悪化時のダウンサイドリスクは大きめ**。

- **例C：ROE 6% / ROA 4% / 自己資本比率 70%**  
  → 攻めてはいないが、資産効率はそこそこ、財務はかなり堅い。  
  → ディフェンシブ高配当株でよく見るタイプで、**「大きくは伸びないが潰れにくい」**イメージ。

- **例D：ROE 3% / ROA 1% / 自己資本比率 30%**  
  → 収益性も資産効率も低く、財務も普通〜やや弱い。  
  → 構造的な競争力やビジネスモデルに疑問が残る水準で、**他に良い選択肢があれば優先度はかなり低い**。
"""
    )
