"""Shared test helpers: tiny PDFs generated on the fly (nothing to commit)."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def make_pdf(path: Path, first_width: int, pages: int = 1, **encrypt) -> Path:
    """Create a PDF whose pages are first_width, first_width + 1, ... points wide.

    The unique widths act as a "fingerprint", so tests can tell exactly which
    pages ended up where.
    """
    writer = PdfWriter()
    for offset in range(pages):
        writer.add_blank_page(width=first_width + offset, height=200)
    if encrypt:
        writer.encrypt(**encrypt)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def widths(path: Path):
    """The page widths of a PDF, as ints."""
    return [int(round(float(page.mediabox.width))) for page in PdfReader(str(path)).pages]


class TempDirTestCase(unittest.TestCase):
    """A TestCase that gets a fresh temporary directory as ``self.dir``."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
