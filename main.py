"""Run pydeef straight from a source checkout:  python main.py

This is also the entry script used when building a standalone executable with
PyInstaller (see the README).
"""

import sys
from pathlib import Path

# Allow running without `pip install .` (the package lives in ./src).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pydeef.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
