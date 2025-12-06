import streamlit as st

from data_fetch import convert_ticker, get_price_and_meta
from indicators import compute_indicators


def setup_page():
    st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
    st.title("🔍買いシグナルチェッカー")


def _evaluate_environment(tech: dict, qvt_score: float) -> tuple[int, str]:
    """
    QVTベースの環境評価スコア（0〜3）とラベルを返す。

    - トレンドフラグ: 中期トレンドが良好か（trend_conditionsのうち2つ以上がTrue）
    - 短期フラグ: Tスコア >= 60 かつ「落ちるナイフ」ではない
    - QVTフラグ: QVTスコア >= 60

    合計 0〜3 を 4段階ラベルに変換。
    """
    trend_conditions = tech.get("trend_conditions", [])
    t_score = float(tech.get("t_score", 0.0))
    timing_label = tech.get("timing_label", "")

    # トレンド良好判定（3つの条件のうち2つ以上満たしていれば1点）
    trend_ok_count = sum(1 for c in trend_conditions if c)
    trend_flag = 1 if trend_ok_count >= 2 else 0

    # 短期タイミング良好判定
    short_flag = 1 if (t_score >= 60 and "落ちるナイフ" not in timing_label) else 0

    # QVT良好判定
    qvt_flag = 1 if qvt_score >= 60 else 0

    env_score = trend_flag + short_flag + qvt_flag

    if env_score == 3:
        label = "環境◎（中期・短期・総合のすべてが良好）"
    elif env_score == 2:
        label = "環境◯（一部に弱みはあるが、総合的には良好）"
    elif env_score == 1:
        label = "環境△（局所的にのみ魅力あり）"
    else:
        label = "環境×（総合的には見送り候補）"

    return env_score, label


def render_app():
    setup_page()

    # ------------ API Key チェック ------------
    if "ALPHA_VANTAGE_API_KEY" not in st.secrets:
        st.error("ALPHA_VANTAGE_API_KEY が st.secrets に設定されていません。")
        st.stop()

    # ------------ 入力 ------------
    user_input = st.text_input("ティッカーを入力（例：7203, 8306.T, AAPL）", value="")
    ticker = convert_ticker(user_input)

    if not ticker:
        st.stop()

    # ------------ データ取得 ------------
    try:
        base = get_price_and_meta(ticker)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    df = base["df"]
    close_col = base["close_col"]
    close = base["close"]
    previous_close = base["previous_close"]
    high_52w = base["high_52w"]
    low_52w = base["low_52w"]
    company_name = base["company_name"]
    dividend_yield = base["dividend_yield"]

    # ファンダ系
    eps = base.get("eps")
    bps = base.get("bps")
    eps_fwd = base.get("eps_fwd")
    per_fwd = base.get("per_fwd")
    roe = base.get("roe")
    roa = base.get("roa")
    equity_ratio = base.get("equity_ratio")

    # ------------ テクニカル + QVT スコア計算 ------------
    try:
        tech = compute_indicators(
            df,
            close_col,
            high_52w,
            low_52w,
            eps=eps,
            bps=bps,
            eps_fwd=eps_fwd,
            per_fwd=per_fwd,
            roe=roe,
            roa=roa,
            equity_ratio=equity_ratio,
            dividend_yield=dividend_yield,
        )
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # ------------ 価格の色 ------------
    if close > previous_close:
        price_color = "red"
    elif close < previous_close:
        price_color = "green"
    else:
        price_color = "black"

    # ------------ ヘッダー部分（価格 + PER/PBR + MA）------------
    st.markdown("---")
    st.markdown(f"## 📌 {ticker}（{company_name}）")

    per_val = tech.get("per")
    pbr_val = tech.get("pbr")
    per_str = f"{per_val:.2f}倍" if per_val is not None else "—"
    pbr_str = f"{pbr_val:.2f}倍" if pbr_val is not None else "—"

    per_fwd_val = tech.get("per_fwd")
    per_fwd_str = f"{per_fwd_val:.2f}倍" if per_fwd_val is not None else "—"

    html_header = (
        f"**現在価格**: "
        f"<span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span><br>"
        f"（前日終値: {previous_close:.2f}）  <br><br>"
        f"**PER**: {per_str} ｜ **予想PER**: {per_fwd_str} ｜ **PBR**: {pbr_str}  <br><br>"
        f"**25MA**: {tech['ma25']:.2f} {tech['arrow25']} ｜ "
        f"**50MA**: {tech['ma50']:.2f} {tech['arrow50']} ｜ "
        f"**75MA**: {tech['ma75']:.2f} {tech['arrow75']}"
    )
    st.markdown(html_header, unsafe_allow_html=True)

    # ------------ RSI / BB / 配当 / 高値掴みアラート ------------
    st.markdown(
        f"""
**RSI**: {tech["rsi"]:.1f} ｜ **BB判定**: {tech["bb_icon"]} {tech["bb_text"]}
        """
    )

    if tech.get("high_price_alert"):
        st.warning("⚠️ 高値掴みリスク（高値圏に近い水準です）")

    if dividend_yield is not None:
        st.markdown(f"**予想配当利回り（過去1年ベース）**: {dividend_yield:.2f}%")

    # ================================
    # 🧩 QVT スコア + タブ構成
    # ================================
    st.markdown("---")
    st.markdown("### 🧩 QVTスコア（質×値札×タイミング）")

    q_score = float(tech.get("q_score", 0.0))
    v_score = float(tech.get("v_score", 0.0))
    t_score = float(tech.get("t_score", 0.0))
    qvt_score = float(tech.get("qvt_score", 0.0))
    timing_label = tech.get("timing_label", "")

    # 環境評価（QVT＋トレンド＋短期）
    env_score, env_label = _evaluate_environment(tech, qvt_score)

    # --- タブ構成 ---
    tab_t, tab_q, tab_v, tab_qvt = st.tabs(
        ["T（押し目・タイミング）", "Q（ビジネスの質）", "V（バリュエーション）", "QVT（総合）"]
    )

    # ================================
    # 🟦 Tタブ：押し目・タイミング
    # ================================
    with tab_t:
        st.subheader("⏰ T（タイミング）")

        col_t_main, col_env = st.columns(2)

        with col_t_main:
            st.metric("Tスコア（タイミング）", f"{t_score:.1f} / 100")
            st.caption(f"タイミング評価: {timing_label}")

        with col_env:
            st.metric("環境スコア（0〜3）", f"{env_score} / 3")
            st.caption(env_label)

        st.markdown("---")
        st.markdown("#### 📌 裁量買いレンジ（目安）")

        # 順張りモードかどうか
        is_trend_mode = tech.get("t_mode") == "trend" or tech["trend_conditions"][0]

        if is_trend_mode:
            # 順張り：25MAと50MAの平均を中心に、少し上まで許容
            center_price = (tech["ma25"] + tech["ma50"]) / 2
            upper_price = center_price * 1.03
            lower_price = max(center_price * 0.95, tech["bb_lower1"])

            st.markdown("**モード**: 📈 順張り（上昇トレンド押し目狙い）")

            st.markdown(
                f"""
- 中心価格（目安）: **{center_price:.2f}**
- 買い検討レンジ（目安）: **{lower_price:.2f} 〜 {upper_price:.2f}**
- コメント: {tech.get("trend_comment", "トレンド判定コメントなし")}
                """
            )

        else:
            # 逆張り：25MA と BB−1σ の中間を中心、少し広めのレンジ
            center_price = (tech["ma25"] + tech["bb_lower1"]) / 2
            upper_price = center_price * 1.08
            lower_price = center_price * 0.97

            st.markdown("**モード**: 🧮 逆張り（下落 or 調整局面の押し目狙い）")

            st.markdown(
                f"""
- 中心価格（目安）: **{center_price:.2f}**
- 買い検討レンジ（目安）: **{lower_price:.2f} 〜 {upper_price:.2f}**
- コメント: {tech.get("contr_comment", "逆張り判定コメントなし")}
                """
            )

        st.info(
            "※ 裁量買いレンジはテクニカル指標に基づく目安です。"
            "実際のエントリーはポジションサイズやPF全体のバランスも加味して判断してください。"
        )

    # ================================
    # 🟩 Qタブ：ビジネスの質
    # ================================
    with tab_q:
        st.subheader("🏢 Q（ビジネスの質）")

        st.metric("Qスコア", f"{q_score:.1f} / 100")

        if roe is not None or roa is not None or equity_ratio is not None:
            st.markdown("#### 財務・収益性の概要")
            st.markdown(
                f"""
- ROE: **{roe:.1f}%**  *（自己資本利益率）*  
- ROA: **{roa:.1f}%**  *（総資産利益率）*  
- 自己資本比率: **{equity_ratio:.1f}%**
                """
            )
        else:
            st.caption("ROE / ROA / 自己資本比率の一部または全部が取得できていません。")

        st.markdown("---")
        st.caption(
            "Qスコアは ROE / ROA / 自己資本比率 をもとに 0〜100 に正規化した指標です。"
            "セクターごとの“普通〜優良”の感覚は異なるため、スコアとあわせて生の数値も確認してください。"
        )

    # ================================
    # 🟨 Vタブ：バリュエーション
    # ================================
    with tab_v:
        st.subheader("💰 V（バリュエーション）")

        st.metric("Vスコア", f"{v_score:.1f} / 100")

        st.markdown("#### バリュエーション指標")
        st.markdown(
            f"""
- PER（実績）: **{per_str}**  
- 予想PER: **{per_fwd_str}**  
- PBR: **{pbr_str}**  
- 配当利回り: **{dividend_yield:.2f}%**  
            """
            if dividend_yield is not None
            else f"""
- PER（実績）: **{per_str}**  
- 予想PER: **{per_fwd_str}**  
- PBR: **{pbr_str}**  
- 配当利回り: **—（取得不可）**  
            """
        )

        st.markdown("---")
        st.caption(
            "Vスコアは PER / PBR / 配当利回り をもとに 0〜100 に正規化した指標です。"
            "ディフェンシブ株・グロース株など、セクターごとに“割安 / 割高”の基準は異なるため、"
            "スコアとあわせて生の指標をセクター感覚で評価してください。"
        )

    # ================================
    # 🟥 QVTタブ：総合評価
    # ================================
    with tab_qvt:
        st.subheader("🧮 QVT（総合評価）")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Q（質）", f"{q_score:.1f} / 100")
        with col2:
            st.metric("V（値札）", f"{v_score:.1f} / 100")
        with col3:
            st.metric("T（タイミング）", f"{t_score:.1f} / 100")
        with col4:
            st.metric("QVT総合スコア", f"{qvt_score:.1f} / 100")

        st.markdown("---")

        st.markdown("#### 総合コメント（使い方の目安）")

        if qvt_score >= 70:
            msg = "総合的にかなり魅力的な水準。PF全体とのバランスを見つつ、主力候補として検討してよいレベル。"
        elif qvt_score >= 60:
            msg = "総合的に“買い検討”レベル。エントリータイミングやロット調整を意識しつつ、分割での参加を検討。"
        elif qvt_score >= 50:
            msg = "悪くはないが、他候補との比較やセクター特性を踏まえて慎重に。無理に弾を使う必要はないゾーン。"
        else:
            msg = "総合力としてはやや物足りない水準。よほどのテーマ性やPF内での役割がない限り、見送りも選択肢。"

        st.write(msg)

        st.markdown("---")
        st.caption(
            "QVTスコアは Q・V・T を同等ウェイトで平均した指標です。"
            "最終的な投資判断では、セクター特性・テーマ性・ポートフォリオ全体の役割を加味して、"
            "自分の“違和感”も含めて上書き評価してください。"
        )
