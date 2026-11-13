"""Entry point: ``python -m pydeef`` (also installed as the ``pydeef`` command)."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__

TKINTER_HELP = """\
pydeef needs Tkinter, which is not available in this Python installation.

  Debian / Ubuntu :  sudo apt install python3-tk
  Fedora          :  sudo dnf install python3-tkinter
  Arch            :  sudo pacman -S tk
  macOS           :  use the installer from python.org (or: brew install python-tk)
  Windows         :  re-run the Python installer and tick "tcl/tk and IDLE"
"""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pydeef",
        description="pydeef - merge PDFs and extract pages with a simple desktop app.",
    )
    parser.add_argument("--version", action="version", version=f"pydeef {__version__}")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print Tk version and check the bundled logo/icon images, then exit",
    )
    args = parser.parse_args(argv)

    try:
        import tkinter  # noqa: F401
    except ImportError:
        if sys.stderr:
            sys.stderr.write(TKINTER_HELP)
        return 1

    from .gui import diagnose, run

    if args.diagnose:
        return diagnose()
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
