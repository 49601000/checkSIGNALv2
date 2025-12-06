# data_fetch.py
from typing import Optional, Tuple
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import streamlit as st  # ← 追加：FMPのAPIキーをst.secretsから取得

IRBANK_BASE = "https://irbank.net/"
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
    yfinance.Ticker.dividends を使うので、
    yfinance へのリクエストは download とは別に 1 回増える前提。
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
# IRBANK から EPS / BPS / PER予 を取得（日本株用）
# ===========================================================
def get_eps_bps_irbank(
    code: str,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    IRBANK の『株式情報 / 指標』ページから
    - EPS（連 or 単）    → 実績EPS
    - BPS（連 or 単）    → 実績BPS
    - PER予              → 予想PER

    を 1 回のリクエストで取得する。

    Parameters
    ----------
    code : str
        '2801' のような数値 4〜5 桁部分を想定（'.T' などは付けない）

    Returns
    -------
    (eps_actual, bps_actual, per_fwd)
        いずれか取得できない場合は None
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
        # Streamlit のログ用
        print(f"[IRBANK] request error ({code}): {e}")
        return None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    def extract_number_near(label: str) -> Optional[float]:
        """
        ページ内で label にマッチするテキストノードを見つけ、
        そのノード自身と、近くのテキストノードから数字を探して float 化する。

        「PER予 18.46倍」のようにラベルと数字が
        同じテキストノードに含まれているケースも拾えるようにする。
        """
        node = soup.find(string=re.compile(re.escape(label)))
        if not node:
            return None

        cur = node
        # node 自身 + その後ろ数ノードをチェック
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

    # EPS / BPS（連）優先、なければ単体 or 汎用ラベルをフォールバック
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

    # PER予（予想PER）
    per_fwd = extract_number_near("PER予")

    return eps, bps, per_fwd


# ===========================================================
# FMP API から US 銘柄の EPS / BPS / 予想EPS を取得
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


def get_us_fundamentals_fmp(
    symbol: str,
    price: float,
    api_key: str,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    FMP から US 銘柄の実績 EPS / BPS / 予想EPS を取得し、
    予想EPS から PER予 も計算して返す。

    Returns
    -------
    (eps_actual, bps_actual, per_fwd, eps_fwd)
    """
    eps: Optional[float] = None
    bps: Optional[float] = None
    per_fwd: Optional[float] = None
    eps_fwd: Optional[float] = None

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

    # 予想PER = price / 予想EPS
    if eps_fwd not in (None, 0.0) and price > 0:
        per_fwd = price / eps_fwd

    return eps, bps, per_fwd, eps_fwd


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
    - 米国株コードなら FMP で 実績EPS / BPS / 予想EPS を取得し、
      そこから予想PER も計算
    - 日本株コードなら IRBANK で 実績EPS / BPS / PER予 を取得し、
      そこから予想EPSも計算する。

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

    # --- EPS / BPS / 予想PER / 予想EPS ---
    eps: Optional[float] = None          # 実績EPS
    bps: Optional[float] = None          # 実績BPS
    per_fwd: Optional[float] = None      # 予想PER
    eps_fwd: Optional[float] = None      # 予想EPS

    # 日本株判定
    is_jp = False
    code_for_irbank: Optional[str] = None
    if ticker.endswith(".T"):
        is_jp = True
        code_for_irbank = ticker.replace(".T", "")
    elif ticker.isdigit() and len(ticker) <= 5:
        is_jp = True
        code_for_irbank = ticker

    if is_jp:
        # --- 日本株: IRBANK ---
        if code_for_irbank is not None:
            eps, bps, per_fwd = get_eps_bps_irbank(code_for_irbank)
            # IRBANK の予想PERから予想EPSを逆算
            if per_fwd not in (None, 0.0) and close > 0:
                eps_fwd = close / per_fwd
    else:
        # --- 米国株など: FMP ---
        fmp_key = None
        try:
            fmp_key = st.secrets["FMP_API_KEY"]
        except Exception:
            print("[FMP] st.secrets['FMP_API_KEY'] が設定されていません。US指標は取得しません。")

        if fmp_key:
            eps, bps, per_fwd, eps_fwd = get_us_fundamentals_fmp(
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
        # IRBANK / FMP 系
        "eps": eps,           # 実績EPS
        "bps": bps,           # 実績BPS
        "per_fwd": per_fwd,   # 予想PER
        "eps_fwd": eps_fwd,   # 予想EPS
    }
