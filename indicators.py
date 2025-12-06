# data_fetch.py
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from functools import lru_cache
import re


def convert_ticker(ticker: str) -> str:
    """
    日本株コードの場合に自動で .T を付与。
    例: "7203" -> "7203.T"
    """
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) <= 5 and not ticker.endswith(".T"):
        return ticker + ".T"
    return ticker


def _compute_dividend_yield_from_df(df: pd.DataFrame, close_col: str, close: float):
    """
    yf.download(..., actions=True) で付いてくる Dividends 列から
    過去1年分の配当を集計して利回り（%）を計算。
    """
    # Dividends 列を探す（MultiIndex flatten 済み想定）
    div_col = next((c for c in df.columns if "Dividends" in c), None)
    if div_col is None or close <= 0:
        return None

    divs = df[div_col]
    if not isinstance(divs, pd.Series) or divs.empty:
        return None

    # index を datetime にそろえる
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
    if last_year_divs.empty:
        return None

    annual_div = float(last_year_divs.sum())
    return (annual_div / close) * 100.0 if close > 0 else None


@lru_cache(maxsize=256)
def get_eps_bps_irbank(code: str):
    """
    IRBANKから EPS（連）/ BPS（連） を1回だけ取得する。
    code: '7203' のような4桁コード
    """
    url = f"https://irbank.net/{code}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception:
        return None, None

    soup = BeautifulSoup(res.text, "html.parser")

    def _find_number_after(label: str):
        # "EPS（連）" などの文字列を含むタグを探す
        tag = soup.find(string=lambda s: s and label in s)
        if not tag:
            return None
        # 次に出てくる「数字を含むテキスト」を拾う
        next_text = tag.find_next(string=lambda s: s and any(ch.isdigit() for ch in s))
        if not next_text:
            return None
        text = next_text.strip()
        m = re.search(r"([\d,]+(?:\.\d+)?)", text)
        if not m:
            return None
        return float(m.group(1).replace(",", ""))

    eps = _find_number_after("EPS（連）")
    bps = _find_number_after("BPS（連）")
    return eps, bps


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


def get_price_and_meta(ticker: str, period: str = "365d", interval: str = "1d"):
    """
    株価データとメタ情報を取得して返す。
    - yfinance.download(actions=True) で価格＋配当を一括取得
    - IRBANK から EPS/BPS を取得（日本株コードのみ）
    失敗時は ValueError を投げる。
    """
    try:
        # actions=True で Dividends 列を含める
        df = yf.download(ticker, period=period, interval=interval, actions=True)
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

    # 配当利回り（過去1年・Dividends列から）
    dividend_yield = _compute_dividend_yield_from_df(df, close_col, close)

    # 日本株なら IRBANK から EPS/BPS
    eps, bps = None, None
    code_for_irbank = None
    if ticker.endswith(".T"):
        code_for_irbank = ticker.replace(".T", "")
    elif ticker.isdigit() and len(ticker) <= 5:
        code_for_irbank = ticker

    if code_for_irbank:
        eps, bps = get_eps_bps_irbank(code_for_irbank)

    # 銘柄名は yfinance.info で取る（API 1回）
    ticker_obj = yf.Ticker(ticker)
    company_name = _get_company_name(ticker_obj, ticker)

    return {
        "df": df,
        "close_col": close_col,
        "close": close,
        "previous_close": previous_close,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "company_name": company_name,
        "dividend_yield": dividend_yield,
        "eps": eps,    # IRBANKから取得
        "bps": bps,    # IRBANKから取得
    }
