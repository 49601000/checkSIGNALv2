# checkSIGNALv2
任意の銘柄が買いシグナル点灯しているか確認するよ。

アプリ構成
app/
  ├── main.py
  ├── ui_components.py   ← 軽量化された共通UIヘルパー
  ├── ui_qtab.py         ← Qタブ専用
  ├── ui_vtab.py         ← Vタブ専用
  ├── ui_ttab.py         ← Tタブ専用
  ├── ui_qvt.py          ← QVT総合タブ
  └── utils.py


モジュールの構成
modules/
  ├── indicators.py       ← 純テクニカル指標計算のみ（RSI・MA・BB・傾き）
  ├── t_logic.py          ← タイミング判定ロジック（押し目、 BB判定、Tスコア）
  ├── q_logic.py          ← Qスコア（財務の質）ロジック
  ├── valuation.py        ← Vスコア（割安性）ロジック
  ├── q_correction.py     ← セクター補正（あなた仕様）
  ├── data_fetch.py       ← データ取得（既存）
  └── __init__.py
