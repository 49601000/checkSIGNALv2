import sys
import os

# --- プロジェクトルートを sys.path に追加 ---
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT)
sys.path.append(os.path.join(ROOT, "app"))
sys.path.append(os.path.join(ROOT, "modules"))

from app.main import main

if __name__ == "__main__":
    main()
