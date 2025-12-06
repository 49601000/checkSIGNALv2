# data_fetch.py
from typing import Optional, Tuple
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import streamlit as st

# -----------------------------------------------------------
# 定数
# -----------------------------------------------------------
IRBANK_BASE = "https://irbank.net/"
# ★ FMP は stable エンドポイントを使う
FMP_BASE_STABLE = "https://financialmodelingprep.com/stable"

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
    過去1年分の配当から配当利回り（%）を計算
    """
    divs = ticker_obj.dividends

    if not isinstance(divs, pd.Series) or len(divs) == 0 or close <= 0:
        return None

    divs.index = pd.to_datetime(divs.index, errors="coerce")
    divs = divs.dropna()

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
    yfinance.info から銘柄名を取得。なければティッカーで代用
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
# FMP から EPS/BPS（米株など）: stable/ratios-ttm
# -----------------------------------------------------------
def get_us_eps_bps_from_fmp(
    symbol: str,
    api_key: Optional[str] = None,
    debug: bool = False,
) -> Tuple[Optional[float], Optional[float]]:
    """
    FMP の stable /ratios-ttm から epsTTM / bvpsTTM を取得。

    ※ free プラン or endpoint 権限によっては 403 が返り、
      その場合は (None, None) を返す。
    """
    key = api_key or FMP_API_KEY
    if not key:
        if debug:
            print("[FMP] API key not set")
        return None, None

    # stable エンドポイント（docs 仕様に合わせて symbol= クエリ形式）
    url = f"{FMP_BASE_STABLE}/ratios-ttm?symbol={symbol}&apikey={key}"

    if debug:
        print(f"[FMP] request -> {url}")

    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        if debug:
            print(f"[FMP] request failed ({symbol}): {e}")
        return None, None

    if debug:
        print(f"[FMP] status={resp.status_code}")
        # 403 のときのメッセージ確認用
        try:
            print(resp.text[:200])
        except Exception:
            pass

    # 403 はほぼ権限エラーなので素直に諦める
    if resp.status_code == 403:
        return None, None

    try:
        resp.raise_for_status()
    except Exception as e:
        if debug:
            print(f"[FMP] HTTP error ({symbol}): {e}")
        return None, None

    try:
        data = resp.json()
    except Exception as e:
        if debug:
            print(f"[FMP] json error ({symbol}): {e}, text={resp.text[:200]}")
        return None, None

    # stable 側の返却形式が list or {"ratiosTTM":[...]} の両対応
    if isinstance(data, dict) and "ratiosTTM" in data:
        records = data.get("ratiosTTM") or []
    elif isinstance(data, list):
        records = data
    else:
        if debug:
            print(f"[FMP] unexpected payload ({symbol}): {data}")
        return None, None

    if not records:
        return None, None

    ratios = records[0] or {}

    eps_ttm = ratios.get("epsTTM") or ratios.get("netIncomePerShareTTM")
    bps_ttm = ratios.get("bvpsTTM") or ratios.get("bookValuePerShareTTM")

    if debug:
        print(f"[FMP] parsed ({symbol}) eps={eps_ttm}, bps={bps_ttm}")

    try:
        eps = float(eps_ttm) if eps_ttm not in (None, "", 0) else None
    except (TypeError, ValueError):
        eps = None

    try:
        bps = float(bps_ttm) if bps_ttm not in (None, "", 0) else None
    except (TypeError, ValueError):
        bps = None

    return eps, bps


# -----------------------------------------------------------
# メイン：価格 + メタ情報 + EPS/BPS/予想EPS
# -----------------------------------------------------------
def get_price_and_meta(
    ticker: str,
    period: str = "180d",
    interval: str = "1d",
    debug: bool = False,
):
    """
    - yfinance.download で OHLCV
    - yfinance.Ticker で銘柄名・配当
    - JPX: IRBANK から EPS/BPS/PER予 → 予想EPS を逆算
    - それ以外（米国株など）：FMP stable/ratios-ttm → EPS/BPS
      取得できなければ yfinance.info からの簡易計算にフォールバック
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

    # 52週高値・安値（この期間内で代用）
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
        # 東証：IRBANK 利用
        code_for_irbank = ticker.replace(".T", "") if ticker.endswith(".T") else ticker
        eps, bps, per_fwd = get_eps_bps_irbank(code_for_irbank)

        if per_fwd not in (None, 0.0) and close > 0:
            eps_fwd = close / per_fwd

    else:
        # 米国株など：まず FMP stable を試す
        eps, bps = get_us_eps_bps_from_fmp(ticker, debug=debug)

        # FMP で取れなかった場合は yfinance.info から簡易計算で補完
        if eps is None or bps is None:
            try:
                info = ticker_obj.info or {}
            except Exception:
                info = {}

            if eps is None:
                eps_candidate = (
                    info.get("trailingEps")
                    or info.get("epsTrailingTwelveMonths")
                    or info.get("epsForward")
                )
                try:
                    eps = float(eps_candidate)
                except (TypeError, ValueError):
                    eps = None

            if bps is None:
                pb = info.get("priceToBook")
                try:
                    pb = float(pb)
                    if pb not in (None, 0) and close > 0:
                        bps = close / pb
                except (TypeError, ValueError):
                    bps = None

    if debug:
        print(
            "[DEBUG fundamentals]",
            {"ticker": ticker, "eps": eps, "bps": bps, "eps_fwd": eps_fwd, "per_fwd": per_fwd},
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
        "eps": eps,        # 実績EPS
        "bps": bps,        # 実績BPS
        "per_fwd": per_fwd,  # JPX: PER予
        "eps_fwd": eps_fwd,  # JPX: 予想EPS
    }
