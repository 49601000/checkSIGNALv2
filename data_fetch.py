# data_fetch.py
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def convert_ticker(ticker: str) -> str:
    """
    日本株コードの場合に自動で .T を付与。
    例: "7203" -> "7203.T"
    """
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) <= 5 and not ticker.endswith(".T"):
        return ticker + ".T"
    return ticker


def _compute_dividend_yield(ticker_obj: yf.Ticker, close: float):
    """
    過去1年分の配当から配当利回り（%）を計算
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
    yfinance.info から銘柄名を取得。なければティッカーで代用。
    """
    name = None
    try:
        info = ticker_obj.info or {}
        name = info.get("longName") or info.get("shortName")
    except Exception:
        name = None

    if not name:
        name = fallback_ticker
    return name


def get_price_and_meta(ticker: str, period: str = "180d", interval: str = "1d"):
    """
    株価データとメタ情報を取得して返す。
    失敗時は ValueError を投げる。
    """
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

    ticker_obj = yf.Ticker(ticker)
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
    }


# data_fetch.py
import re
import requests
from bs4 import BeautifulSoup

IRBANK_BASE = "https://irbank.net/"

def get_eps_bps_irbank(code: str) -> tuple[float | None, float | None]:
    """
    IRBANK の『株式情報』ページから EPS（連）/ BPS（連） を 1 回だけ取得する。

    Parameters
    ----------
    code : str
        '2801' のような数値 4 桁〜5 桁部分を想定（'.T' などは付けない）

    Returns
    -------
    (eps, bps) : tuple[float | None, float | None]
        取得できなかった場合は None
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
        # Streamlit 側のコンソール確認用
        print(f"[IRBANK] request error ({code}): {e}")
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    def extract_number_after(label: str) -> float | None:
        """
        ページ内で label（例: 'EPS（連）'）にマッチするテキストを見つけ、
        その直後付近の文字列から「数字っぽいところ」を抜き出して float 化する。
        """
        node = soup.find(string=re.compile(re.escape(label)))
        if not node:
            return None

        cur = node
        # 近くのテキストノードを 6 ステップくらいまで探索して数字を探す
        for _ in range(6):
            cur = cur.find_next(string=True)
            if not cur:
                break
            m = re.search(r"([\d,]+(?:\.\d+)?)", cur)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    return None
        return None

    # EPS / BPS（連）優先、なければ単体 or プレーンなラベルをフォールバック
    eps = (
        extract_number_after("EPS（連）")
        or extract_number_after("EPS（単）")
        or extract_number_after("EPS")
    )
    bps = (
        extract_number_after("BPS（連）")
        or extract_number_after("BPS（単）")
        or extract_number_after("BPS")
    )

    return eps, bps
