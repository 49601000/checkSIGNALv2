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
# ティッカー補正 / JPX 判定
# -----------------------------------------------------------
def convert_ticker(ticker: str) -> str:
    """
    日本株コード (数字4〜5桁) の場合は自動で .T を付与。
    その他はそのまま大文字化して返す。
    """
    t = ticker.strip().upper()
    if t.isdigit() and len(t) <= 5 and not t.endswith(".T"):
        return t + ".T"
    return t


def is_jpx_ticker(ticker: str) -> bool:
    """
    末尾 .T か、数字4〜5桁だけなら JPX 銘柄とみなす。
    """
    t = ticker.strip().upper()
    return t.endswith(".T") or (t.isdigit() and len(t) <= 5)


# -----------------------------------------------------------
# 配当利回り計算（yfinance.Ticker.dividends 利用）
# -----------------------------------------------------------
def _compute_dividend_yield(ticker_obj: yf.Ticker, close: float) -> Optional[float]:
    """
    過去1年分の配当から配当利回り（%）を計算。
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
    yfinance.info  から銘柄名を取得。なければティッカーで代用。
    """
    name = None
    try:
        info = ticker_obj.info or {}
        name = info.get("longName") or info.get("shortName")
    except Exception:
        name = None

    return name or fallback_ticker


# -----------------------------------------------------------
# IRBANK から 実績EPS / BPS / PER予 を取得（JPX用）
# -----------------------------------------------------------
def get_eps_bps_irbank(
    code: str,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    IRBANK の『株式情報 / 指標』ページから
    - EPS（連 or 単）    → 実績EPS
    - BPS（連 or 単）    → 実績BPS
    - PER予              → 予想PER
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
# FMP から US 銘柄の EPS/BPS を取得（ratios-ttm 利用）
# -----------------------------------------------------------
def get_us_eps_bps_from_fmp(
    symbol: str,
    close: float,
    api_key: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    FMP /ratios-ttm から EPS/BPS を取得。
    - epsTTM / bvpsTTM があればそれを使用
    - なければ peTTM / pbTTM と株価 close から逆算
    """
    key = api_key or FMP_API_KEY
    if not key:
        print("[FMP] API key が設定されていません")
        return None, None

    url = f"{FMP_BASE}/ratios-ttm/{symbol}?apikey={key}"
    print(f"[FMP] request -> {url}")

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[FMP] request error ({symbol}): {e}")
        return None, None

    try:
        data = resp.json()
    except Exception as e:
        print(f"[FMP] json error ({symbol}): {e}, text={resp.text[:200]}")
        return None, None

    print(f"[FMP] raw json ({symbol}): {data}")

    if not isinstance(data, list) or not data:
        print(f"[FMP] unexpected payload ({symbol}): {data}")
        return None, None

    ratios = data[0] or {}

    eps_ttm = ratios.get("epsTTM") or ratios.get("netIncomePerShareTTM")
    bps_ttm = ratios.get("bvpsTTM") or ratios.get("bookValuePerShareTTM")
    pe_ttm = ratios.get("peTTM") or ratios.get("priceEarningsRatioTTM")
    pb_ttm = ratios.get("pbTTM") or ratios.get("priceToBookRatioTTM")

    eps = eps_ttm
    bps = bps_ttm

    # 足りない場合は PER/PBR と株価から逆算
    if eps in (None, 0, 0.0) and pe_ttm not in (None, 0, 0.0) and close > 0:
        eps = close / pe_ttm
    if bps in (None, 0, 0.0) and pb_ttm not in (None, 0, 0.0) and close > 0:
        bps = close / pb_ttm

    print(
        f"[FMP] parsed ({symbol}) eps={eps} (raw_eps={eps_ttm}, pe={pe_ttm}), "
        f"bps={bps} (raw_bps={bps_ttm}, pb={pb_ttm})"
    )

    return eps, bps


# -----------------------------------------------------------
# メイン：価格 + メタ情報 + EPS/BPS/予想EPS 取得
# -----------------------------------------------------------
def get_price_and_meta(
    ticker: str,
    period: str = "180d",
    interval: str = "1d",
):
    """
    株価データとメタ情報を取得して返す。
    - yfinance.download で OHLCV
    - yfinance.Ticker で銘柄名・配当
    - 日本株コードなら IRBANK で 実績EPS / BPS / PER予 を取得し、そこから予想EPSも計算
    - それ以外（米国株など）は FMP から EPS/BPS を取得
    """
    # --- 価格データ（yfinance.download）---
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

    # --- ファンダメンタル関連の初期値 ---
    eps: Optional[float] = None          # 実績EPS
    bps: Optional[float] = None          # 実績BPS
    per_fwd: Optional[float] = None      # PER予（JPXのみ）
    eps_fwd: Optional[float] = None      # 予想EPS（JPXのみ）

    # --- 日本株 (IRBANK) or 米株 (FMP) の分岐 ---
    if is_jpx_ticker(ticker):
        # "2801.T" -> "2801" に変換
        code_for_irbank = ticker.replace(".T", "") if ticker.endswith(".T") else ticker
        eps, bps, per_fwd = get_eps_bps_irbank(code_for_irbank)

        # 予想PERが取れていて株価も正なら、そこから予想EPSを逆算
        if per_fwd not in (None, 0.0) and close > 0:
            eps_fwd = close / per_fwd
    else:
        # 米国銘柄など → FMP の ratios-ttm から EPS/BPS を取得
        eps, bps = get_us_eps_bps_from_fmp(ticker, close)

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
        "eps": eps,           # 実績EPS
        "bps": bps,           # 実績BPS
        "per_fwd": per_fwd,   # JPX: PER予
        "eps_fwd": eps_fwd,   # JPX: 予想EPS
    }
