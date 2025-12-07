from typing import Optional, Tuple, Dict
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
ALPHA_BASE = "https://www.alphavantage.co/query"

# 銘柄名キャッシュ（IRBANK / Alpha Vantage のレスポンスから埋める）
COMPANY_NAME_CACHE: Dict[str, str] = {}

# Streamlit Secrets から Alpha Vantage API キー取得
ALPHA_VANTAGE_API_KEY: Optional[str] = st.secrets.get(
    "ALPHA_VANTAGE_API_KEY", None
)


# -----------------------------------------------------------
# ティッカー補正 / 市場判定
# -----------------------------------------------------------
def convert_ticker(ticker: str) -> str:
    """
    4〜5桁の数字のみなら自動で .T を付与（東証）
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
# 共通ユーティリティ
# -----------------------------------------------------------
def _safe_float(x) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _compute_dividend_yield(
    ticker_obj: yf.Ticker, close: float
) -> Optional[float]:
    """
    yfinance.Ticker.dividends から過去1年分の配当利回り（%）を計算。
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


def _get_company_name(ticker_obj: yf.Ticker, fallback_ticker: str) -> str:
    """
    可能なら yfinance を叩く前に、モジュール内キャッシュから銘柄名を取得。
    なければ最後の手段として yfinance.info を見る。
    """
    key = fallback_ticker.strip().upper()

    # 1️⃣ まず自前キャッシュをチェック
    cached = COMPANY_NAME_CACHE.get(key)
    if cached:
        return cached

    # 2️⃣ キャッシュがなければ従来どおり yfinance.info にフォールバック
    name = None
    try:
        info = ticker_obj.info or {}
        name = info.get("longName") or info.get("shortName")
    except Exception:
        name = None

    return name or fallback_ticker

def _clean_jpx_company_name(name: str) -> str:
    """
    IRBANK のタイトルから会社名を抽出した際に付く
    「|株式情報」「｜株式情報」「| 株式情報」などの
    全パターンを除去する。
    """
    if not isinstance(name, str):
        return name

    # 全角・半角バー + 任意スペース + 株式情報
    patterns = [
        "株価/株式情報",
        "株価・株式情報",
        "｜ 株式情報",
        "｜株式情報",
        "| 株式情報",
        "|株式情報",
        "株式情報",
    ]

    for p in patterns:
        if p in name:
            name = name.split(p)[0]

    # よく残るゴミ文字（全角/半角スペース・バー・ハイフンなど）を削る
    return name.strip(" 　-|｜")


# -----------------------------------------------------------
# IRBANK から 日本株の EPS/BPS/PER予/ROE/ROA/自己資本比率 を取得
# -----------------------------------------------------------
def get_jpx_fundamentals_irbank(
    code: str,
) -> Tuple[
    Optional[float],  # eps
    Optional[float],  # bps
    Optional[float],  # per_fwd
    Optional[float],  # roe (%)
    Optional[float],  # roa (%)
    Optional[float],  # equity_ratio (%)
]:
    """
    IRBANK の『株式指標』ページから
    - EPS（連 or 単）          → 実績EPS
    - BPS（連 or 単）          → 実績BPS
    - PER予                    → 予想PER
    - ROE（連）                → ROE %
    - ROA（連）                → ROA %
    - 株主資本比率（連）       → 自己資本比率 %

    ついでに <title> から会社名を拾ってモジュール内キャッシュに保存する。
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
        return None, None, None, None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    # 会社名を <title> からざっくり取得してキャッシュ
    try:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title_text = title_tag.string.strip()
            # 例: 「2801 キッコーマン｜株式情報 - IRBANK」 などを想定
            raw_name = title_text.split("【")[0]
            company_name = _clean_jpx_company_name(raw_name)
            if company_name:
                # "2801" / "2801.T" どちらで呼ばれても拾えるよう両方キャッシュ
                COMPANY_NAME_CACHE[code] = company_name
                COMPANY_NAME_CACHE[f"{code}.T"] = company_name
    except Exception as e:
        print(f"[IRBANK] name parse error ({code}): {e}")


    def extract_number_near(label: str) -> Optional[float]:
        """
        ラベル文字列の近くに出てくる数値（% や 円/株 含む）をざっくり抜き出す。
        """
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

    # EPS / BPS
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

    # 予想PER（存在しない銘柄もある）
    per_fwd = extract_number_near("PER予")

    # ROE / ROA / 自己資本比率（いずれも % 表記）
    roe = extract_number_near("ROE（連）") or extract_number_near("ROE")
    roa = extract_number_near("ROA（連）") or extract_number_near("ROA")
    equity_ratio = (
        extract_number_near("株主資本比率（連）")
        or extract_number_near("株主資本比率")
    )

    return eps, bps, per_fwd, roe, roa, equity_ratio


# -----------------------------------------------------------
# Alpha Vantage から 米株の EPS/BPS/ROE/ROA/自己資本比率(近似) を取得
# -----------------------------------------------------------
def get_us_fundamentals_alpha(
    symbol: str,
) -> Tuple[
    Optional[float],  # eps
    Optional[float],  # bps
    Optional[float],  # roe (%)
    Optional[float],  # roa (%)
    Optional[float],  # equity_ratio (% approx)
]:
    """
    Alpha Vantage の OVERVIEW から
    - EPS
    - BookValue
    - ReturnOnEquityTTM
    - ReturnOnAssetsTTM
    を取得し、ROE/ROA は %、自己資本比率は ROA/ROE から近似値を算出。

    併せて "Name" を会社名としてキャッシュする。
    """
    eps = bps = roe_pct = roa_pct = equity_ratio_pct = None

    api_key = ALPHA_VANTAGE_API_KEY
    if not api_key:
        print("[Alpha] API key not set")
        return eps, bps, roe_pct, roa_pct, equity_ratio_pct

    params = {
        "function": "OVERVIEW",
        "symbol": symbol,
        "apikey": api_key,
    }

    try:
        resp = requests.get(ALPHA_BASE, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[Alpha] request error ({symbol}): {e}")
        return eps, bps, roe_pct, roa_pct, equity_ratio_pct

    try:
        data = resp.json()
    except Exception as e:
        print(f"[Alpha] json error ({symbol}): {e}, text={resp.text[:200]}")
        return eps, bps, roe_pct, roa_pct, equity_ratio_pct

    if not isinstance(data, dict) or not data:
        print(f"[Alpha] unexpected payload ({symbol}): {data}")
        return eps, bps, roe_pct, roa_pct, equity_ratio_pct

    # 会社名をキャッシュ
    name_val = data.get("Name")
    if isinstance(name_val, str) and name_val.strip():
        COMPANY_NAME_CACHE[symbol.upper()] = name_val.strip()

    eps_val = _safe_float(data.get("EPS"))
    bps_val = _safe_float(data.get("BookValue"))
    roe_raw = _safe_float(data.get("ReturnOnEquityTTM"))
    roa_raw = _safe_float(data.get("ReturnOnAssetsTTM"))

    if eps_val is not None:
        eps = eps_val
    if bps_val is not None:
        bps = bps_val

    # Alpha の ROE/ROA は 0.15 (=15%) のような小数なので % に変換
    if roe_raw is not None:
        roe_pct = roe_raw * 100.0
    if roa_raw is not None:
        roa_pct = roa_raw * 100.0

    # 自己資本比率 ≒ ROA / ROE（同じ期間の数値前提）
    if roe_raw not in (None, 0.0) and roa_raw not in (None, 0.0):
        approx = roa_raw / roe_raw  # 0.04 / 0.10 = 0.4
        # 0〜1 の範囲にあるものだけ採用（明らかに変な値は捨てる）
        if 0.0 < approx < 1.0:
            equity_ratio_pct = approx * 100.0

    return eps, bps, roe_pct, roa_pct, equity_ratio_pct


# -----------------------------------------------------------
# メイン：価格 + メタ情報 + ファンダメンタル
# -----------------------------------------------------------
def get_price_and_meta(
    ticker: str,
    period: str = "180d",
    interval: str = "1d",
):
    """
    - yfinance.download で OHLCV
    - yfinance.Ticker で銘柄名・配当
    - JPX: IRBANK から EPS/BPS/PER予/ROE/ROA/自己資本比率
    - US:  Alpha Vantage から EPS/BPS/ROE/ROA/自己資本比率(近似)
    """
    # --- 価格データ（yfinance）---
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

    # --- ファンダメンタルの初期値 ---
    eps: Optional[float] = None
    bps: Optional[float] = None
    per_fwd: Optional[float] = None
    eps_fwd: Optional[float] = None  # 予想EPS（現状は JPX のみ想定）
    roe_pct: Optional[float] = None
    roa_pct: Optional[float] = None
    equity_ratio_pct: Optional[float] = None

    # --- 日本株 or 米株の分岐（先にファンダを取得して会社名キャッシュを埋める） ---
    if is_jpx_ticker(ticker):
        # "2801.T" -> "2801" に変換
        code_for_irbank = ticker.replace(".T", "") if ticker.endswith(".T") else ticker
        (
            eps,
            bps,
            per_fwd,
            roe_pct,
            roa_pct,
            equity_ratio_pct,
        ) = get_jpx_fundamentals_irbank(code_for_irbank)

        # PER予が取れていて株価も正なら、そこから予想EPSを逆算
        if per_fwd not in (None, 0.0) and close > 0:
            eps_fwd = close / per_fwd

    else:
        # 米国銘柄など → Alpha Vantage OVERVIEW
        (
            eps,
            bps,
            roe_pct,
            roa_pct,
            equity_ratio_pct,
        ) = get_us_fundamentals_alpha(ticker)

    # --- yfinance.Ticker（銘柄名 + 配当利回り）---
    ticker_obj = yf.Ticker(ticker)
    # ここでまず IRBANK / Alpha が埋めたキャッシュを見て、なければ info にフォールバック
    company_name = _get_company_name(ticker_obj, ticker)
    dividend_yield = _compute_dividend_yield(ticker_obj, close)

    return {
        "df": df,
        "close_col": close_col,
        "close": close,
        "previous_close": previous_close,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "company_name": company_name,
        "dividend_yield": dividend_yield,
        # ファンダメンタル
        "eps": eps,                 # 実績EPS
        "bps": bps,                 # 実績BPS
        "per_fwd": per_fwd,         # JPX: 予想PER
        "eps_fwd": eps_fwd,         # JPX: 予想EPS
        "roe": roe_pct,             # ROE (%)
        "roa": roa_pct,             # ROA (%)
        "equity_ratio": equity_ratio_pct,  # 自己資本比率 (%、USは近似)
    }
