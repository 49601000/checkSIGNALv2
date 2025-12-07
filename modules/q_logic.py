"""
Q（ビジネスの質）スコア算出専用モジュール
ROE / ROA / 自己資本比率 を正規化して 0〜100 に変換する
"""

from typing import Optional


def score_quality(
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
) -> float:

    raw = 0.0
    max_raw = 50 + 25 + 20  # ROE + ROA + 自己資本比率 = 95

    if roe is not None:
        if roe <= 0:
            raw += 0
        elif roe < 5:
            raw += 10
        elif roe < 10:
            raw += 20
        elif roe < 15:
            raw += 30
        elif roe < 20:
            raw += 40
        elif roe < 25:
            raw += 45
        else:
            raw += 50

    if roa is not None:
        if roa <= 0:
            raw += 0
        elif roa < 2:
            raw += 5
        elif roa < 4:
            raw += 10
        elif roa < 6:
            raw += 15
        elif roa < 8:
            raw += 20
        else:
            raw += 25

    if equity_ratio is not None:
        if equity_ratio < 20:
            raw += 0
        elif equity_ratio < 30:
            raw += 3
        elif equity_ratio < 40:
            raw += 6
        elif equity_ratio < 50:
            raw += 10
        elif equity_ratio < 60:
            raw += 15
        else:
            raw += 20

    return max(0.0, min(100.0, raw / max_raw * 100.0))
