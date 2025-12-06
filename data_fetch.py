# data_fetch.py
from typing import Optional, Tuple
from datetime import datetime, timedelta

import requests
import yfinance as yf
import pandas as pd
import streamlit as st  # FMPのAPIキーをst.secretsから取得

FMP_BASE = "https://financialmodelingprep.com/api/v3"


# -----------------------------------------------------------
# ティッカー補正（日本株コードの場合に .T を付与）
# -----------------------------------------------------------
def convert_ticker(ticker: str) -> str:
    """
    日本株コードの場合に自動で .T を付与。
    例: "7203" -> "7203.T"
    """
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) <= 5 and not ticker.endswith(".T"):
        return ticker + ".T"
    return ticker


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
# 銘柄名取得（yfinance.info）
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


# ===========================================================
# FMP 共通ラッパー
# ===========================================================
def _fmp_get(path: str, api_key: str, params: Optional[dict] = None):
    """
    FMP の共通 GET ラッパー。失敗時は None を返す。
    """
    if not api_key:
        return None

    url = f"{FMP_BASE}{path}"
    q = {"apikey": api_key}
    if params:
        q.update(params)

    try:
        resp = requests.get(url, params=q, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[FMP] request error ({path}): {e}")
        return None


# ===========================================================
# FMP から EPS / BPS / 予想EPS を取得（US も JPX も共通）
# ===========================================================
def get_fundamentals_fmp(
    symbol: str,
    price: float,
    api_key: str,
) -> Tuple[
    Optional[float],  # eps
    Optional[float],  # bps
    Optional[float],  # eps_fwd
    Optional[float],  # per
    Optional[float],  # pbr
    Optional[float],  # per_fwd
]:
    """
    FMP から実績EPS / BPS / 予想EPSを取得し、
    そこから PER / PBR / 予想PER も計算する。

    symbol は "NVDA", "AAPL", "7203.T" など
    """
    eps: Optional[float] = None
    bps: Optional[float] = None
    eps_fwd: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    per_fwd: Optional[float] = None

    # --- 実績 EPS: income-statement ---
    income = _fmp_get(f"/income-statement/{symbol}", api_key, {"limit": 1})
    if isinstance(income, list) and income:
        row = income[0]
        raw = row.get("eps") or row.get("epsDiluted")
        try:
            if raw not in (None, ""):
                eps = float(raw)
        except Exception:
            eps = None

    # --- BPS: balance-sheet-statement（株主資本 ÷ 発行済株式数） ---
    bs = _fmp_get(f"/balance-sheet-statement/{symbol}", api_key, {"limit": 1})
    if isinstance(bs, list) and bs:
        row = bs[0]
        equity = row.get("totalStockholdersEquity") or row.get("totalEquity")
        shares = (
            row.get("commonStockSharesOutstanding")
            or row.get("commonSharesOutstanding")
        )
        try:
            if equity not in (None, "") and shares not in (None, "", 0):
                equity_val = float(equity)
                shares_val = float(shares)
                if shares_val > 0:
                    bps = equity_val / shares_val
        except Exception:
            bps = None

    # --- 予想 EPS: analyst-estimates ---
    estimates = _fmp_get(f"/analyst-estimates/{symbol}", api_key, {"limit": 1})
    if isinstance(estimates, list) and estimates:
        row = estimates[0]
        raw_est = (
            row.get("estimatedEpsAvg")
            or row.get("epsAvg")
            or row.get("estimatedEpsHigh")
        )
        try:
            if raw_est not in (None, ""):
                eps_fwd = float(raw_est)
        except Exception:
            eps_fwd = None

    # --- PER / PBR / 予想PER 計算 ---
    if eps not in (None, 0.0) and price > 0:
        per = price / eps
    if bps not in (None, 0.0) and price > 0:
        pbr = price / bps
    if eps_fwd not in (None, 0.0) and price > 0:
        per_fwd = price / eps_fwd

    return eps, bps, eps_fwd, per, pbr, per_fwd


# ===========================================================
# メイン：価格 + メタ情報 + EPS/BPS/予想EPS 取得
# ===========================================================
def get_price_and_meta(
    ticker: str,
    period: str = "180d",
    interval: str = "1d",
):
    """
    株価データとメタ情報を取得して返す。
    - yfinance.download で OHLCV
    - yfinance.Ticker で銘柄名・配当
    - FMP で 実績EPS / BPS / 予想EPS を取得し、
      そこから PER / PBR / 予想PER も計算する（US も JPX も共通）

    失敗時は ValueError を投げる。
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

    # --- FMP からファンダメンタル取得（US / JP 共通）---
    fmp_key = None
    try:
        fmp_key = st.secrets["FMP_API_KEY"]
    except Exception:
        print("[FMP] st.secrets['FMP_API_KEY'] が設定されていません。ファンダ指標は取得しません。")

    eps: Optional[float] = None
    bps: Optional[float] = None
    eps_fwd: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    per_fwd: Optional[float] = None

    if fmp_key:
        eps, bps, eps_fwd, per, pbr, per_fwd = get_fundamentals_fmp(
            symbol=ticker,
            price=close,
            api_key=fmp_key,
        )

    return {
        "df": df,
        "close_col": close_col,
        "close": close,
        "previous_close": previous_close,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "company_name": company_name,
        "dividend_yield": dividend_yield,
        # FMP 系
        "eps": eps,           # 実績EPS
        "bps": bps,           # 実績BPS
        "eps_fwd": eps_fwd,   # 予想EPS
        "per": per,           # 実績PER（close / eps）
        "pbr": pbr,           # 実績PBR（close / bps）
        "per_fwd": per_fwd,   # 予想PER（close / eps_fwd）
    }
