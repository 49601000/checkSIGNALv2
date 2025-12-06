# data_fetch.py
from typing import Optional, Tuple
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import streamlit as st

IRBANK_BASE = "https://irbank.net/"
FMP_BASE = "https://financialmodelingprep.com/api/v3"

# Streamlit Secrets から API キー取得
FMP_API_KEY: Optional[str] = st.secrets.get("FMP_API_KEY")


# -----------------------------------------------------------
# ティッカー補正 / 市場判定
# -----------------------------------------------------------
def convert_ticker(ticker: str) -> str:
    """
    4〜5桁の数字だけなら自動で .T を付与（東証）
    それ以外は大文字にしてそのまま返す（米株など）
    """
    t = ticker.strip().upper()
    if not t:
        return ""
    if t.endswith(".T"):
        return t
    if t.isdigit() and 4 <= len(t) <= 5:
        return t + ".T"
    return t


def is_jpx_ticker(ticker: str) -> bool:
    """東証銘柄かどうかの簡易判定"""
    t = ticker.strip().upper()
    if t.endswith(".T"):
        return True
    if t.isdigit() and 4 <= len(t) <= 5:
        return True
    return False


# -----------------------------------------------------------
# 配当利回り（yfinance）
# -----------------------------------------------------------
def _compute_dividend_yield(ticker_obj: yf.Ticker, close: float) -> Optional[float]:
    """
    yfinance.Ticker.dividends から過去 1 年分の配当利回り（％）を計算。
    """
    divs = ticker_obj.dividends

    if not isinstance(divs, pd.Series) or len(divs) == 0 or close <= 0:
        return None

    # index を datetime64[ns] に統一
    divs.index = pd.to_datetime(divs.index, errors="coerce")
    divs = divs.dropna()

    # タイムゾーン除去
    try:
        if getattr(divs.index, "tz", None) is not None:
            divs.index = divs.index.tz_localize(None)
    except Exception:
        pass

    one_year_ago = datetime.now() - timedelta(days=365)
    one_year_ago = one_year_ago.replace(tzinfo=None)

    last_year_divs = divs[divs.index >= one_year_ago]
    if len(last_year_divs) == 0:
        return None

    annual_div = last_year_divs.sum()
    return float(annual_div / close * 100.0) if close > 0 else None


# -----------------------------------------------------------
# 銘柄名取得
# -----------------------------------------------------------
def _get_company_name(ticker_obj: yf.Ticker, fallback_ticker: str) -> str:
    """
    yfinance.info から銘柄名を取得。なければティッカーで代用。
    """
    name = None
    try:
        info = ticker_obj.info or {}
        name = info.get("longName") or info.get("shortName")
    except Exception:
        name = None

    return name or fallback_ticker


# -----------------------------------------------------------
# IRBANK から EPS/BPS/PER予（日本株）
# -----------------------------------------------------------
def get_eps_bps_irbank(
    code: str,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    IRBANK の『株式情報 / 指標』ページから
    - EPS（連 or 単） → 実績EPS
    - BPS（連 or 単） → 実績BPS
    - PER予           → 予想PER
    """
    url = f"{IRBANK_BASE}{code}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": IRBANK_BASE,
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[IRBANK] request error ({code}): {e}")
        return None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    def extract_number_near(label: str) -> Optional[float]:
        node = soup.find(string=re.compile(re.escape(label)))
        if not node:
            return None

        cur = node
        # node 自身 + その後ろ数ノードをチェックして数値を探す
        for _ in range(8):
            if cur is None:
                break
            text = str(cur)
            m = re.search(r"([\d,]+(?:\.\d+)?)", text)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    return None
            cur = cur.find_next(string=True)
        return None

    eps = (
        extract_number_near("EPS（連）")
        or extract_number_near("EPS（単）")
        or extract_number_near("EPS")
    )
    bps = (
        extract_number_near("BPS（連）")
        or extract_number_near("BPS（単）")
        or extract_number_near("BPS")
    )
    per_fwd = extract_number_near("PER予")

    return eps, bps, per_fwd


# -----------------------------------------------------------
# FMP から EPS/BPS（米株など）
# -----------------------------------------------------------
def get_us_eps_bps_from_fmp(
    symbol: str,
    api_key: Optional[str] = None,
    debug: bool = True,          # ★ デフォルトでデバッグ ON
) -> Tuple[Optional[float], Optional[float]]:
    """
    FMP /ratios-ttm から epsTTM / bvpsTTM を取得。
    PER/PBR は compute_indicators 側で price/eps, price/bps から計算する。

    debug=True のときは Streamlit 上にレスポンスの中身を出す。
    """
    key = api_key or FMP_API_KEY
    if not key:
        msg = "[FMP] API key not set"
        print(msg)
        if debug:
            st.warning(msg)
        return None, None

    url = f"{FMP_BASE}/ratios-ttm/{symbol}?apikey={key}"

    # ★ ここで URL をそのまま確認できるようにしておく
    if debug:
        st.write("🔍 FMP request URL:", url)

    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        msg = f"[FMP] request error ({symbol}): {e}"
        print(msg)
        if debug:
            st.error(msg)
        return None, None

    if debug:
        st.write("FMP status code:", resp.status_code)
        st.write("FMP raw response (head):", resp.text[:500])

    # HTTP ステータスが 200 以外ならここで終了
    try:
        resp.raise_for_status()
    except Exception as e:
        msg = f"[FMP] HTTP error ({symbol}): {e}"
        print(msg)
        if debug:
            st.error(msg)
        return None, None

    # JSON 解析
    try:
        data = resp.json()
    except Exception as e:
        msg = f"[FMP] json error ({symbol}): {e}"
        print(msg)
        if debug:
            st.error(msg)
        return None, None

    if debug:
        st.write("FMP parsed JSON:", data)

    # 想定は list[dict] 形式
    if not isinstance(data, list) or not data:
        msg = f"[FMP] unexpected payload ({symbol}): {data}"
        print(msg)
        if debug:
            st.warning(msg)
        return None, None

    ratios = data[0] or {}

    # キー名はいくつかパターンがあるので OR で順に見る
    eps_ttm = ratios.get("epsTTM") or ratios.get("netIncomePerShareTTM")
    bps_ttm = ratios.get("bvpsTTM") or ratios.get("bookValuePerShareTTM")

    if debug:
        st.write("FMP extracted fields:",
                 {"epsTTM": eps_ttm, "bvpsTTM": bps_ttm})

    eps = float(eps_ttm) if eps_ttm not in (None, "", 0) else None
    bps = float(bps_ttm) if bps_ttm not in (None, "", 0) else None

    return eps, bps

# -----------------------------------------------------------
# メイン：価格 + メタ情報 + EPS/BPS/予想EPS
# -----------------------------------------------------------
def get_price_and_meta(
    ticker: str,
    period: str = "180d",
    interval: str = "1d",
):
    """
    - yfinance.download で OHLCV
    - yfinance.Ticker で銘柄名・配当
    - JPX: IRBANK から EPS/BPS/PER予 → 予想EPS を逆算
    - それ以外（米国株など）：FMP から epsTTM/bvpsTTM
    """
    # --- 株価データ ---
    try:
        df = yf.download(ticker, period=period, interval=interval)
    except Exception as e:
        raise ValueError(f"株価データ取得エラー: {e}")

    if df.empty:
        raise ValueError("株価データが取得できませんでした。")

    # yfinance のマルチカラム対応
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(col).strip() for col in df.columns]

    # Close 列特定
    try:
        close_col = next(c for c in df.columns if "Close" in c)
    except StopIteration:
        raise ValueError("終値（Close）列が見つかりませんでした。")

    if len(df[close_col]) < 2:
        raise ValueError("データ日数が不足しています（2営業日未満）。")

    close = float(df[close_col].iloc[-1])
    previous_close = float(df[close_col].iloc[-2])

    # 52週高値・安値（取得期間内で代用）
    high_52w = float(df[close_col].max())
    low_52w = float(df[close_col].min())

    # --- yfinance.Ticker（銘柄名 + 配当利回り）---
    ticker_obj = yf.Ticker(ticker)
    company_name = _get_company_name(ticker_obj, ticker)
    dividend_yield = _compute_dividend_yield(ticker_obj, close)

    # --- ファンダメンタル関連 ---
    eps: Optional[float] = None
    bps: Optional[float] = None
    per_fwd: Optional[float] = None
    eps_fwd: Optional[float] = None

    if is_jpx_ticker(ticker):
        # "2801.T" -> "2801" に変換して IRBANK に投げる
        code_for_irbank = ticker.replace(".T", "") if ticker.endswith(".T") else ticker
        eps, bps, per_fwd = get_eps_bps_irbank(code_for_irbank)

        # 予想PERが取れていて株価も正なら、そこから予想EPSを逆算
        if per_fwd not in (None, 0.0) and close > 0:
            eps_fwd = close / per_fwd
    else:
        # 米国銘柄など → FMP の ratios-ttm から EPS/BPS を取得
        eps, bps = get_us_eps_bps_from_fmp(ticker)

    return {
        "df": df,
        "close_col": close_col,
        "close": close,
        "previous_close": previous_close,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "company_name": company_name,
        "dividend_yield": dividend_yield,
        # IRBANK / FMP からのファンダメンタル
        "eps": eps,          # 実績EPS
        "bps": bps,          # 実績BPS
        "per_fwd": per_fwd,  # JPX: PER予
        "eps_fwd": eps_fwd,  # JPX: 予想EPS
    }
