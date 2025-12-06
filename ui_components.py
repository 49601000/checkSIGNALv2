import streamlit as st

from data_fetch import convert_ticker, get_price_and_meta
from indicators import compute_indicators


def setup_page():
    st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
    st.title("🔍買いシグナルチェッカー")


def render_app():
    setup_page()

    # ------------ Alpha Vantage API Key の存在チェック ------------
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

    # ファンダ系
    dividend_yield = base.get("dividend_yield")
    eps = base.get("eps")              # 実績 EPS
    bps = base.get("bps")              # 実績 BPS
    eps_fwd = base.get("eps_fwd")      # 予想 EPS（あれば）
    per_fwd = base.get("per_fwd")      # 予想 PER（あれば）
    roa = base.get("roa")              # ROA（%）
    roe = base.get("roe")              # ROE（%）
    equity_ratio = base.get("equity_ratio")  # 自己資本比率（%）

    # ------------ テクニカル + Q/V/T スコア計算 ------------
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
            roa=roa,
            roe=roe,
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

    # ------------ ヘッダー部分 ------------
    st.markdown("---")
    st.markdown(f"## 📌 {ticker}（{company_name}）")

    # PER / PBR
    per_val = tech.get("per")
    pbr_val = tech.get("pbr")
    per_str = f"{per_val:.2f}倍" if per_val is not None else "—"
    pbr_str = f"{pbr_val:.2f}倍" if pbr_val is not None else "—"

    # 予想 PER（あれば）
    per_fwd_val = tech.get("per_fwd")
    per_fwd_str = f"{per_fwd_val:.2f}倍" if per_fwd_val is not None else "—"

    html_header = (
        f"**現在価格**: "
        f"<span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span>  <br>"
        f"（前日終値: {previous_close:.2f}）  <br><br>"
        f"**PER**: {per_str} ｜ **PBR**: {pbr_str}  <br>"
        f"**予想PER**: {per_fwd_str}  <br>"
    )
    st.markdown(html_header, unsafe_allow_html=True)

    if dividend_yield is not None:
        st.markdown(f"**予想配当利回り（過去1年ベース）**: {dividend_yield:.2f}%")

    # ------------ QVT サマリー（おすすめ構成の「ダッシュボード」部分）------------
    st.markdown("---")
    st.markdown("### 🧮 Q / V / T サマリー")

    q_score = tech.get("q_score")
    v_score = tech.get("v_score")
    t_score = tech.get("t_score")
    total_qvt = tech.get("total_qvt_score")
    t_mode = tech.get("t_mode")  # "trend" or "contrarian"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Q：ビジネスの質", f"{q_score:.0f} / 100" if q_score is not None else "—")
    col2.metric("V：バリュエーション", f"{v_score:.0f} / 100" if v_score is not None else "—")
    col3.metric(
        "T：タイミング",
        f"{t_score:.0f} / 100" if t_score is not None else "—",
    )
    col4.metric(
        "総合 QVT",
        f"{total_qvt:.0f} / 100" if total_qvt is not None else "—",
    )

    if t_mode == "trend":
        st.caption("T は **順張り視点**（25MA ＞ 50MA ＞ 75MA）のタイミングスコアを表示中。")
    elif t_mode == "contrarian":
        st.caption("T は **逆張り視点**（下降・横ばい）のタイミングスコアを表示中。")

    # ------------ タブ構成：ファンダメンタルズ / テクニカル＋裁量レンジ ------------
    tab_fund, tab_tech = st.tabs(["📚 ファンダメンタルズ（Q / V）", "📉 テクニカル（T）＋裁量レンジ"])

    # ========================
    # 📚 ファンダメンタルズ（Q / V）
    # ========================
    with tab_fund:
        st.markdown("#### Q：ビジネスの質")

        roa_val = tech.get("roa")
        roe_val = tech.get("roe")
        eq_val = tech.get("equity_ratio")
        q_sub = tech.get("q_subscores", {})

        st.markdown(
            f"""
| 指標 | 値 | スコア |
|---|---|---|
| ROA（総資産利益率） | {f"{roa_val:.1f}%" if roa_val is not None else "—"} | {q_sub.get("roa_score", "—")} |
| ROE（自己資本利益率） | {f"{roe_val:.1f}%" if roe_val is not None else "—"} | {q_sub.get("roe_score", "—")} |
| 自己資本比率 | {f"{eq_val:.1f}%" if eq_val is not None else "—"} | {q_sub.get("equity_ratio_score", "—")} |
| **Q 合計** |  | **{f"{q_score:.1f}" if q_score is not None else "—"} / 100** |
"""
        )

        st.markdown("#### V：バリュエーション")

        v_sub = tech.get("v_subscores", {})

        st.markdown(
            f"""
| 指標 | 値 | スコア |
|---|---|---|
| PER | {per_str} | {v_sub.get("per_score", "—")} |
| PBR | {pbr_str} | {v_sub.get("pbr_score", "—")} |
| 予想配当利回り | {f"{dividend_yield:.2f}%" if dividend_yield is not None else "—"} | {v_sub.get("dividend_yield_score", "—")} |
| **V 合計** |  | **{f"{v_score:.1f}" if v_score is not None else "—"} / 100** |
"""
        )

    # ========================
    # 📉 テクニカル（T）＋裁量レンジ
    # ========================
    with tab_tech:
        # --- テクニカル概要 ---
        st.markdown("#### テクニカル概況")

        st.markdown(
            f"""
**25MA**: {tech['ma25']:.2f} {tech['arrow25']} ｜ 
**50MA**: {tech['ma50']:.2f} {tech['arrow50']} ｜ 
**75MA**: {tech['ma75']:.2f} {tech['arrow75']}  

**RSI**: {tech["rsi"]:.1f} ｜ **BB判定**: {tech["bb_icon"]} {tech["bb_text"]}
"""
        )

        st.markdown(
            f"**タイミングスコア (T)**: "
            f"{f'{t_score:.1f} / 100' if t_score is not None else '—'}"
        )

        # 押し目シグナル
        st.markdown(f"### {tech['signal_icon']} {tech['signal_text']}")
        st.progress(tech["signal_strength"] / 3)

        st.markdown("---")
        st.markdown("#### 裁量買いレンジ")

        # 順張り（25 > 50 > 75）
        if tech["trend_conditions"][0]:
            center_price = (tech["ma25"] + tech["ma50"]) / 2
            upper_price = center_price * 1.03
            lower_price = max(center_price * 0.95, tech["bb_lower1"])

            st.markdown("### 📈 ＜順張り＞裁量買いレンジ")

            st.markdown(
                f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 25MA ＞ 50MA ＞ 75MA | {"○" if tech["trend_conditions"][0] else "×"} |
| 短期傾向 | MA25 が横ばい〜緩やか上昇 | {"○" if tech["trend_conditions"][1] else "×"} |
| 割高否定 | ブルスコアが60点以上で「押し目」と判定 | {tech["highprice_score"]} |
| 中心価格 | 25MA と 50MA の平均 | {center_price:.2f} |
| 上側許容 | ×1.03 | {upper_price:.2f} |
| 下側許容 | ×0.95 または BB-1σ | {lower_price:.2f} |
| 判定 | — | **{tech["trend_comment"]}** |
"""
            )
        # 逆張り（下降 or 横ばい）
        else:
            center_price = (tech["ma25"] + tech["bb_lower1"]) / 2
            upper_price = center_price * 1.08
            lower_price = center_price * 0.97

            st.markdown("### 🧮 ＜逆張り＞裁量買いレンジ")

            st.markdown(
                f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 下降 or 横ばい | {"○" if tech["contrarian_conditions"][0] else "×"} |
| 短期傾向 | MA25 が下降 | {"○" if tech["contrarian_conditions"][1] else "×"} |
| 割安判定 | ベアスコアが60点以上で「割安」と判定 | {tech["low_score"]} |
| 中心価格 | 25MA と BB−1σ の平均 | {center_price:.2f} |
| 上側許容 | ×1.08 | {upper_price:.2f} |
| 下側許容 | ×0.97 | {lower_price:.2f} |
| 判定 | — | **{tech["contr_comment"]}** |
"""
            )
