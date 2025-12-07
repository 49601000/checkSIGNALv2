"""
q_correction.py
----------------

【目的】
本モジュールは、既存の Q スコア（ROE・ROA・自己資本比率に基づく
ビジネスの質評価）に対して、
「セクター特性を加味した補正バイアス」を適用するための補助モジュールである。

既存の Q スコアは、個別企業の絶対的な財務指標に基づいて 0〜100 に正規化される。
しかし、企業が属するセクターの構造的収益性（例：鉄道・インフラは低ROEが普通、
ソフトウェア・半導体は高ROEが普通）を加味しないと、
“本来の平均値”からの乖離を適切に評価できないケースが生じる。

本モジュールの役割は、
    ● 既存 Q スコアを作り直すのではなく  
    ● セクターに対する相対位置をバイアスとして付与し  
    ● 「補正後Q」として投資家の判断材料を拡張する  
という点にある。

【基本思想】
- セクター平均 ROE / ROA を 100 としたときの偏差（±）を計算する
- その偏差を最大 ±20pt の範囲でクリップし、既存 Q スコアに加算する
- 補正後 Q は 0〜100 にクリップして返す
- 補正後 QVT スコアも合わせて再計算する
- 自己資本比率（Equity Ratio）はセクター間差の評価が難しいため補正に使用しない
  （元のQスコア内の絶対評価に委譲する）

【この方式を採用する理由】
- 元の Q スコアの構造や意味を壊さずに “上書き補正” できる
- スコア全体の整合性（Q / V / T の比較可能性）が保たれる
- ユーザーが「補正前 / 補正後」を並べて見た時に直感的に理解しやすい
- 自動計算ではなく「必要な時だけ手動補正」という運用思想に合致する

【注意事項】
- セクター平均値はユーザー入力に依存するため、補正はあくまで裁量ベース
- ROE / ROA のいずれか、またはセクター値が欠損する場合は補正を行わない
- 今後、別方式（絶対評価型Qの作り直し）を追加する場合にも拡張しやすい構成

このモジュールは Q スコアの“代替”ではなく、“補助レイヤー”として設計されている。
"""

from typing import Optional, Dict, Any


def _relative_score(
    actual: Optional[float],
    sector: Optional[float],
    cap: float = 1.5,
) -> Optional[float]:
    """
    実績値 / セクター値 から 0〜100 の相対スコアを計算する簡易関数。

    - ratio = actual / sector
    - ratio が 1.0 なら 70 点ぐらい
    - ratio が cap 以上なら 100 点
    - ratio が 0.0 なら 0 点
    """
    if actual is None or sector in (None, 0):
        return None

    ratio = actual / sector
    ratio = max(0.0, min(cap, ratio))

    # 0〜cap を 0〜100 に線形マッピング
    return round(ratio / cap * 100.0, 1)


def apply_q_correction(
    tech: Dict[str, Any],
    sector_roe: Optional[float],
    sector_roa: Optional[float],
) -> Dict[str, Any]:
    """
    Qタブから呼び出されるメイン関数。

    Parameters
    ----------
    tech : dict
        compute_indicators が返す dict 全体。
    sector_roe : float | None
        ユーザー入力のセクターROE目安（%）。
    sector_roa : float | None
        ユーザー入力のセクターROA目安（%）。

    Returns
    -------
    dict
        {
          "q_base": 元のQスコア,
          "q_corrected": 補正後Qスコア,
          "qvt_corrected": 補正後QVTスコア,
          "roe_rel": ROEの相対スコア,
          "roa_rel": ROAの相対スコア,
        }
    """
    base_q = float(tech.get("q_score", 0.0))
    v_score = float(tech.get("v_score", 0.0))
    t_score = float(tech.get("t_score", 0.0))

    roe = tech.get("roe")
    roa = tech.get("roa")

    roe_rel = _relative_score(roe, sector_roe)
    roa_rel = _relative_score(roa, sector_roa)

    # 相対スコアの平均（有効なものだけ）
    rel_list = [x for x in (roe_rel, roa_rel) if x is not None]

    # 補正係数（セクター偏差をどの程度 Q に反映するか）
    CORRECTION_ALPHA = 0.5  # 0.0〜1.0 で調整
    NEUTRAL_REL = 70.0      # ratio=1.0 付近を「中立」とみなす

    if rel_list:
        rel_avg = sum(rel_list) / len(rel_list)
        rel_delta = rel_avg - NEUTRAL_REL  # ← 偏差ベース

        # 元Qに偏差の一部だけを加算する形で補正
        q_corrected_raw = base_q + CORRECTION_ALPHA * rel_delta

        # スコアは 0〜100 にクリップ
        q_corrected = round(max(0.0, min(100.0, q_corrected_raw)), 1)
    else:
        # セクター値が入ってなければ元のQをそのまま使う
        q_corrected = base_q

    # 補正後Q を使った QVT
    qvt_corrected = round((q_corrected + v_score + t_score) / 3.0, 1)

    return {
        "q_base": base_q,
        "q_corrected": q_corrected,
        "qvt_corrected": qvt_corrected,
        "roe_rel": roe_rel,
        "roa_rel": roa_rel,
    }


        st.info("セクター基準を用いて Q と QVT を補正した結果を表示しています。")

    st.markdown("---")

    st.caption(
        "Q補正は、ROE / ROA をセクター平均と比較したバイアスを付与する簡易モデルです。"
    )
