# data_fetch.py
from typing import Optional, Tuple
import re
from datetime import datetime, timedelta
import os

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd

IRBANK_BASE = "https://irbank.net/"


# -----------------------------------------------------------
# ティッカー補正
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
# IRBANK から 実績EPS / BPS / PER予 を取得（日本株用）
# -----------------------------------------------------------
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
        print(f"[IRBANK] request error ({code}): {e}")
        return None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    def extract_number_near(label: str) -> Optional[float]:
        """
        ページ内で label にマッチするテキストノードを見つけ、
        そのノード自身と、近くのテキストノードから数字を探して float 化する。
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
# FMP から EPS/BPS/PER/PBR を取得（主に米国株用）
# -----------------------------------------------------------
def fetch_fmp_metrics(
    ticker: str,
    api_key: Optional[str],
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Financial Modeling Prep の key-metrics-ttm から
    - epsTTM                     -> EPS
    - bookValuePerShareTTM      -> BPS
    - peRatioTTM / peTTM / priceEarningsRatioTTM -> PER
    - pbRatioTTM / pbTTM / priceToBookRatioTTM   -> PBR

    を取る。失敗時は全部 None を返す。
    """
    if not api_key:
        return None, None, None, None

    # 東証(.T) はここでは扱わない（IRBANK に任せる）
    if ticker.endswith(".T"):
        return None, None, None, None

    base = "https://financialmodelingprep.com/api/v3/key-metrics-ttm"
    url = f"{base}/{ticker}?apikey={api_key}"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[FMP] request error ({ticker}): {e}")
        return None, None, None, None

    if not isinstance(data, list) or len(data) == 0:
        print(f"[FMP] empty response for {ticker}: {data}")
        return None, None, None, None

    row = data[0] or {}

    eps = row.get("epsTTM")
    bps = row.get("bookValuePerShareTTM")

    # PER の候補キーを順番に探す
    per = (
        row.get("peRatioTTM")
        or row.get("peTTM")
        or row.get("priceEarningsRatioTTM")
        or row.get("priceEarningsTTM")
    )

    # PBR の候補キーを順番に探す
    pbr = (
        row.get("pbRatioTTM")
        or row.get("pbTTM")
        or row.get("priceToBookRatioTTM")
    )

    try:
        eps = float(eps) if eps not in (None, "", "NaN") else None
    except Exception:
        eps = None

    try:
        bps = float(bps) if bps not in (None, "", "NaN") else None
    except Exception:
        bps = None

    try:
        per = float(per) if per not in (None, "", "NaN") else None
    except Exception:
        per = None

    try:
        pbr = float(pbr) if pbr not in (None, "", "NaN") else None
    except Exception:
        pbr = None

    return eps, bps, per, pbr


# -----------------------------------------------------------
# メイン：価格 + メタ情報 + EPS/BPS/予想EPS 取得
# -----------------------------------------------------------
def get_price_and_meta(
    ticker: str,
    period: str = "180d",
    interval: str = "1d",
    fmp_api_key: Optional[str] = None,
):
    """
    株価データとメタ情報を取得して返す。
    - yfinance.download で OHLCV
    - yfinance.Ticker で銘柄名・配当
    - 米国株コードなら FMP で EPS/BPS/PER/PBR を取得
    - 日本株コードなら IRBANK で EPS/BPS/PER予 を取得し、
      そこから予想EPSも計算する。

    戻り値 dict は indicators.compute_indicators にそのまま渡せる形。
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

    # --- ファンダ系（EPS/BPS/PERなど）---
    eps: Optional[float] = None          # 実績EPS
    bps: Optional[float] = None          # 実績BPS
    per_fwd: Optional[float] = None      # 予想PER or TTM PER
    eps_fwd: Optional[float] = None      # 予想EPS（IRBANK or FMPから計算用）
    # pbr をここで直接使うことはないが、将来拡張用に取得しておく
    pbr_direct: Optional[float] = None

    # 日本株かどうか
    is_jp = ticker.endswith(".T") or (ticker.isdigit() and len(ticker) <= 5)

    if is_jp:
        # ---- 東証銘柄 → IRBANK ----
        code_for_irbank = ticker.replace(".T", "")
        eps, bps, per_fwd = get_eps_bps_irbank(code_for_irbank)

        # 予想PERが取れていて株価も正なら、そこから予想EPSを逆算
        if per_fwd not in (None, 0.0) and close > 0:
            eps_fwd = close / per_fwd

    else:
        # ---- 米国など → FMP ----
        eps, bps, per_direct, pbr_direct = fetch_fmp_metrics(ticker, fmp_api_key)

        # TTM PER を per_fwd として indicators 側に渡す
        per_fwd = per_direct

        # eps_fwd は今回は特になし（必要なら将来 FMP の forward EPS を使う）
        eps_fwd = None

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
        "eps": eps,           # 実績EPS (日本=IRBANK, 米=FMP epsTTM)
        "bps": bps,           # 実績BPS (同上)
        "per_fwd": per_fwd,   # 日本=IRBANK PER予 / 米=FMP PE TTM
        "eps_fwd": eps_fwd,   # 日本=close/PER予 / 米=None
        # 将来 pbr を使いたくなったとき用
        "pbr_direct": pbr_direct,
    }
