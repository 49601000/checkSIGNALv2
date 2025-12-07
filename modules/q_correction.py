"""
あなた専用の Q 補正（セクター上限値方式）モジュール
"""

def correct_q_score(actual_roe, actual_roa, sector_roe, sector_roa):
    roe_score = min(100, max(0, 100 * actual_roe / sector_roe))
    roa_score = min(100, max(0, 100 * actual_roa / sector_roa))
    return round(roe_score * 0.6 + roa_score * 0.4, 1)
