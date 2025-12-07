"""
V（バリュエーション）スコア算出モジュール
PER / PBR / 配当利回りを 0〜100 に正規化する
"""

from typing import Optional


def score_valuation(
    per: Optional[float],
    pbr: Optional[float],
    dividend_yield: Optional[float],
) -> float:

    raw = 0.0
    max_raw = 30 + 25 + 20  # PER + PBR + Yield = 75

    if per is not None and per > 0:
        if per < 8:
            raw += 30
        elif per < 12:
            raw += 26
        elif per < 20:
            raw += 20
        elif per < 30:
            raw += 10
        elif per < 40:
            raw += 5

    if pbr is not None and pbr > 0:
        if pbr < 0.8:
            raw += 25
        elif pbr < 1.2:
            raw += 20
        elif pbr < 2.0:
            raw += 10
        elif pbr < 3.0:
            raw += 5

    if dividend_yield:
        if dividend_yield >= 5:
            raw += 20
        elif dividend_yield >= 3:
            raw += 16
        elif dividend_yield >= 2:
            raw += 10
        elif dividend_yield >= 1:
            raw += 5

    return max(0.0, min(100.0, raw / max_raw * 100.0))
