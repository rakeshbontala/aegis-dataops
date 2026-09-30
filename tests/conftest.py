"""Ensure the project root is importable regardless of pytest's rootdir
resolution, so `import engine.*` / `import api.*` / `import config.*`
work the same as when running `python -m engine.x.y` from the repo root.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
