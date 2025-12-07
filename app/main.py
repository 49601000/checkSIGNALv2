import streamlit as st

from modules.data_fetch import convert_ticker, get_price_and_meta
from modules.indicators import compute_indicators

from app.ui_components import setup_page, render_header_block
from app.ui_ttab import render_t_tab
from app.ui_qtab import render_q_tab
from app.ui_vtab import render_v_tab
from app.ui_qvt import render_qvt_tab


def main():
    setup_page()

    # --- API Keyチェック ---
    if "ALPHA_VANTAGE_API_KEY" not in st.secrets:
        st.error("ALPHA_VANTAGE_API_KEY が設定されていません。")
        st.stop()

    # --- ティッカー入力 ---
    user_input = st.text_input(
        "ティッカーを入力（例：7203, 8306.T, AAPL）", value=""
    )
    ticker = convert_ticker(user_input)
    if not ticker:
        st.stop()

    # --- データ取得 ---
    try:
        base = get_price_and_meta(ticker)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    df = base["df"]
    close_col = base["close_col"]

    # --- ファンダ & テクニカル計算 ---
    try:
        tech = compute_indicators(
            df,
            close_col,
            base["high_52w"],
            base["low_52w"],
            eps=base.get("eps"),
            bps=base.get("bps"),
            eps_fwd=base.get("eps_fwd"),
            per_fwd=base.get("per_fwd"),
            roe=base.get("roe"),
            roa=base.get("roa"),
            equity_ratio=base.get("equity_ratio"),
            dividend_yield=base.get("dividend_yield"),
        )
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # --- 価格情報・ヘッダー ---
    render_header_block(
        ticker=ticker,
        company_name=base["company_name"],
        close=base["close"],
        previous_close=base["previous_close"],
        tech=tech,
        dividend_yield=base.get("dividend_yield"),
    )

    # --- タブ構成 ---
    tab_t, tab_q, tab_v, tab_qvt = st.tabs(
        ["T（タイミング）", "Q（質）", "V（値札）", "QVT（総合）"]
    )

    with tab_t:
        render_t_tab(tech)

    with tab_q:
        render_q_tab(tech)

    with tab_v:
        render_v_tab(tech)

    with tab_qvt:
        render_qvt_tab(tech)


if __name__ == "__main__":
    main()
