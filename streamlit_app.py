import sys
import os

# --- プロジェクトルート（streamlit_app.py の場所） ---
ROOT = os.path.dirname(os.path.abspath(__file__))

# --- パス追加（絶対にこの順番で！） ---
sys.path.insert(0, ROOT)                            # /
sys.path.insert(0, os.path.join(ROOT, "app"))       # /app
sys.path.insert(0, os.path.join(ROOT, "app", "modules"))  # /app/modules

# Debug: 実際にパスがどうなってるか確認
print("PYTHONPATH:", sys.path)

from app.main import main

if __name__ == "__main__":
    main()
