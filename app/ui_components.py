import streamlit as st


def setup_page():
    st.set_page_config(
        page_title="買いシグナルチェッカー",
        page_icon="📊",
        layout="wide"
    )
    st.title("🔍買いシグナルチェッカー")


def _fmt_float(x, digits: int = 2) -> str:
    """None / 不正値対応付きの float 表示ヘルパー"""
    if x is None:
        return "—"
    try:
        return f"{float(x):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def render_header_block(
    ticker: str,
    company_name: str,
    close: float,
    previous_close: float,
    tech: dict,
    dividend_yield: float,
):
    """共通ヘッダー（価格・PER/PBR・MA の表示）"""

    # 色判定
    if close > previous_close:
        price_color = "red"
    elif close < previous_close:
        price_color = "green"
    else:
        price_color = "black"

    # PER / PBR
    per_val = tech.get("per")
    pbr_val = tech.get("pbr")
    per_fwd_val = tech.get("per_fwd")

    per_str = f"{per_val:.2f}倍" if per_val else "—"
    pbr_str = f"{pbr_val:.2f}倍" if pbr_val else "—"
    per_fwd_str = f"{per_fwd_val:.2f}倍" if per_fwd_val else "—"

    # ---- ここで MA / 矢印を indicators の命名に合わせて取得 ----
    ma_25 = tech.get("ma_25")
    ma_50 = tech.get("ma_50")
    ma_75 = tech.get("ma_75")

    arrow_25 = tech.get("arrow_25", "")
    arrow_50 = tech.get("arrow_50", "")
    arrow_75 = tech.get("arrow_75", "")

    st.markdown("---")
    st.markdown(f"## 📌 {ticker}（{company_name}）")

    html = f"""
    **現在価格**: <span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span><br>
    （前日終値: {previous_close:.2f}）<br><br>

    **PER**: {per_str} ｜ **予想PER**: {per_fwd_str} ｜ **PBR**: {pbr_str}<br><br>

    **25MA**: {_fmt_float(ma_25)} {arrow_25} ｜ 
    **50MA**: {_fmt_float(ma_50)} {arrow_50} ｜ 
    **75MA**: {_fmt_float(ma_75)} {arrow_75}
    """
    st.markdown(html, unsafe_allow_html=True)

    st.markdown(
        f"**RSI**: {tech['rsi']:.1f} ｜ **BB判定**: {tech['bb_icon']} {tech['bb_text']}"
    )

    if tech.get("high_price_alert"):
        st.warning("⚠️ 高値掴みリスク（高値圏に近い水準です）")

    if dividend_yield is not None:
        st.markdown(f"**予想配当利回り**: {dividend_yield:.2f}%")
