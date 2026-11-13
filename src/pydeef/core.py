"""Core PDF operations for pydeef.

This module has **no GUI imports**, so it can be used (and tested) on its own:

    from pydeef.core import merge_pdfs, extract_pages

    merge_pdfs(["a.pdf", "b.pdf"], "merged.pdf")
    extract_pages("book.pdf", "chapter.pdf", "13")
    extract_pages("book.pdf", "intro.pdf", "1-3, 5")

Design notes
------------
* Output files are written to a temporary file first and then moved into place
  with ``os.replace``. If anything fails half-way, an existing output file is
  never left corrupted or half-written.
* All "expected" problems (missing file, password-protected PDF, bad page
  number, ...) raise :class:`PydeefError` with a message that is safe to show
  directly to the user.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Union

from pypdf import PdfReader, PdfWriter
from pypdf.errors import DependencyError

__all__ = [
    "ExtractResult",
    "MergeResult",
    "PydeefError",
    "count_pages",
    "extract_pages",
    "extract_specific_page",
    "merge_pdfs",
    "open_pdf",
    "parse_page_spec",
    "same_file",
    "with_pdf_suffix",
]

PathLike = Union[str, "os.PathLike[str]"]
ProgressCallback = Callable[[int, int], None]


class PydeefError(Exception):
    """An error whose message is meant to be shown to the user."""


# --------------------------------------------------------------------------- #
# Result objects
# --------------------------------------------------------------------------- #
@dataclass
class MergeResult:
    """What :func:`merge_pdfs` did."""

    output: Path
    files: int
    pages: int
    deleted: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExtractResult:
    """What :func:`extract_pages` did."""

    output: Path
    pages: List[int]  # 1-based page numbers, in the order they were written
    source_pages: int  # total pages in the source document


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def with_pdf_suffix(path: PathLike) -> Path:
    """Return ``path`` with a ``.pdf`` extension (added only if it is missing)."""
    candidate = Path(path)
    if candidate.suffix.lower() == ".pdf":
        return candidate
    return candidate.with_name(candidate.name + ".pdf")


def same_file(a: PathLike, b: PathLike) -> bool:
    """True if both paths point at the same file (works even if one is missing)."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _prepare_output(output: PathLike) -> Path:
    if not str(output).strip():
        raise PydeefError("Choose where to save the output file.")
    return with_pdf_suffix(Path(output).expanduser())


def _write_atomic(writer: PdfWriter, output: Path) -> None:
    """Write ``writer`` to ``output`` without ever leaving a partial file behind."""
    if not output.parent.is_dir():
        raise PydeefError(f"The folder does not exist: {output.parent}")

    tmp = output.with_name(f".{output.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "xb") as handle:
            writer.write(handle)
        os.replace(tmp, output)
    except OSError as exc:
        raise PydeefError(f"Could not save '{output.name}': {exc.strerror or exc}") from exc
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def open_pdf(path: PathLike) -> PdfReader:
    """Open a PDF for reading and return a ready-to-use ``PdfReader``.

    PDFs that are encrypted with an *empty* user password (very common) are
    decrypted transparently. Truly password-protected PDFs raise
    :class:`PydeefError`.
    """
    source = Path(path)
    if not source.is_file():
        raise PydeefError(f"File not found: {source}")

    try:
        reader = PdfReader(str(source))
        if reader.is_encrypted and int(reader.decrypt("")) == 0:
            raise PydeefError(
                f"'{source.name}' is password-protected. "
                "Remove the password first, then try again."
            )
        len(reader.pages)  # force the page tree to load so broken files fail early
    except PydeefError:
        raise
    except DependencyError as exc:
        raise PydeefError(
            f"'{source.name}' uses encryption that needs an extra package. "
            "Install it with:  pip install cryptography"
        ) from exc
    except OSError as exc:
        raise PydeefError(f"Could not open '{source.name}': {exc.strerror or exc}") from exc
    except Exception as exc:  # malformed PDFs can raise many different errors
        raise PydeefError(f"'{source.name}' could not be read as a PDF ({exc}).") from exc
    return reader


def count_pages(path: PathLike) -> int:
    """Number of pages in the PDF at ``path``."""
    return len(open_pdf(path).pages)


# --------------------------------------------------------------------------- #
# Page selection ("1-3, 5, 8-")
# --------------------------------------------------------------------------- #
def _to_int(text: str, original: str) -> int:
    if not (text.isascii() and text.isdigit()):
        raise PydeefError(
            f"'{original}' is not a valid page or range. Use numbers like 13 or 1-3, 5."
        )
    return int(text)


def parse_page_spec(spec: str, total_pages: int) -> List[int]:
    """Turn a page specification into a list of 1-based page numbers.

    Supported syntax (commas or semicolons separate items)::

        13          a single page
        1-3         a range (inclusive)
        8-          from page 8 to the last page
        1-3, 5, 8-  any combination

    Pages keep the order they were written in; repeated pages are dropped.
    """
    if total_pages < 1:
        raise PydeefError("The PDF has no pages.")

    cleaned = spec.replace(";", ",").strip()
    tokens = [token.strip() for token in cleaned.split(",") if token.strip()]
    if not tokens:
        raise PydeefError("Enter the page(s) to extract, for example 13 or 1-3, 5.")

    pages: List[int] = []
    seen = set()
    for token in tokens:
        if "-" in token:
            start_text, _, end_text = (part.strip() for part in token.partition("-"))
            start = _to_int(start_text, token)
            end = _to_int(end_text, token) if end_text else total_pages
        else:
            start = end = _to_int(token, token)

        if start < 1 or end < 1:
            raise PydeefError("Page numbers start at 1.")
        if start > end:
            raise PydeefError(f"'{token}' is backwards. Write ranges as 3-7, not 7-3.")
        if end > total_pages:
            raise PydeefError(
                f"Page {end} does not exist - this PDF has {total_pages} "
                f"page{'s' if total_pages != 1 else ''}."
            )

        for number in range(start, end + 1):
            if number not in seen:
                seen.add(number)
                pages.append(number)
    return pages


def _validate_numbers(numbers: Sequence[int], total_pages: int) -> List[int]:
    pages: List[int] = []
    seen = set()
    for number in numbers:
        if not isinstance(number, int) or isinstance(number, bool):
            raise PydeefError(f"'{number}' is not a valid page number.")
        if number < 1 or number > total_pages:
            raise PydeefError(
                f"Page {number} does not exist - this PDF has {total_pages} "
                f"page{'s' if total_pages != 1 else ''}."
            )
        if number not in seen:
            seen.add(number)
            pages.append(number)
    if not pages:
        raise PydeefError("Choose at least one page to extract.")
    return pages


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def merge_pdfs(
    inputs: Sequence[PathLike],
    output: PathLike,
    *,
    delete_old: Optional[PathLike] = None,
    progress: Optional[ProgressCallback] = None,
) -> MergeResult:
    """Merge ``inputs`` (in order) into a single PDF at ``output``.

    Args:
        inputs: Two or more PDF paths. They are merged top to bottom.
        output: Where to save the result (``.pdf`` is added if missing).
            An existing file is replaced atomically.
        delete_old: Optional path of an *old* merged file to delete **after**
            the new file was written successfully. This is the "replace the
            previous merged file" behaviour of the original script.
        progress: Optional ``callback(done, total)`` called after each input
            file has been read.

    Raises:
        PydeefError: for any problem the user can fix (see the message).
    """
    sources = [Path(item).expanduser() for item in inputs]
    if len(sources) < 2:
        raise PydeefError("Add at least two PDF files to merge.")
    out = _prepare_output(output)

    writer = PdfWriter()
    total_pages = 0
    try:
        for index, source in enumerate(sources, start=1):
            reader = open_pdf(source)
            writer.append(reader)
            total_pages += len(reader.pages)
            if progress is not None:
                progress(index, len(sources))
        _write_atomic(writer, out)
    except PydeefError:
        raise
    except Exception as exc:
        raise PydeefError(f"Could not merge the PDFs: {exc}") from exc
    finally:
        writer.close()

    result = MergeResult(output=out, files=len(sources), pages=total_pages)
    if delete_old is not None and str(delete_old).strip():
        _delete_old_file(Path(delete_old).expanduser(), out, result)
    return result


def _delete_old_file(old: Path, new_output: Path, result: MergeResult) -> None:
    """Delete ``old`` after a successful merge; problems become warnings."""
    if old.exists() and same_file(old, new_output):
        result.warnings.append(
            "The old file is the same as the new output, so it was replaced instead of deleted."
        )
    elif not old.exists():
        result.warnings.append(f"Old file not found, nothing to delete: {old}")
    elif not old.is_file():
        result.warnings.append(f"Not a file, so it was not deleted: {old}")
    else:
        try:
            old.unlink()
            result.deleted = old
        except OSError as exc:
            result.warnings.append(
                f"The PDFs were merged, but the old file could not be deleted: "
                f"{exc.strerror or exc}"
            )


# --------------------------------------------------------------------------- #
# Extract
# --------------------------------------------------------------------------- #
def extract_pages(
    input_path: PathLike,
    output: PathLike,
    pages: Union[str, Sequence[int]],
) -> ExtractResult:
    """Copy selected pages of ``input_path`` into a new PDF at ``output``.

    Args:
        input_path: The source PDF (it is never modified).
        output: Where to save the extracted pages (``.pdf`` is added if missing).
        pages: Either a specification string such as ``"13"`` or ``"1-3, 5"``,
            or a sequence of 1-based page numbers.

    Raises:
        PydeefError: if the file can't be read, a page does not exist, or the
            output would overwrite the source file.
    """
    source = Path(input_path).expanduser()
    out = _prepare_output(output)
    if same_file(source, out):
        raise PydeefError(
            "The output file is the same as the source PDF. Choose a different name "
            "so the original is not overwritten."
        )

    reader = open_pdf(source)
    total = len(reader.pages)
    numbers = (
        parse_page_spec(pages, total) if isinstance(pages, str) else _validate_numbers(pages, total)
    )

    writer = PdfWriter()
    try:
        for number in numbers:  # pypdf pages are 0-based; ours are 1-based
            writer.add_page(reader.pages[number - 1])
        _write_atomic(writer, out)
    except PydeefError:
        raise
    except Exception as exc:
        raise PydeefError(f"Could not extract the pages: {exc}") from exc
    finally:
        writer.close()

    return ExtractResult(output=out, pages=numbers, source_pages=total)


def extract_specific_page(
    input_pdf_path: PathLike, output_pdf_path: PathLike, page_number: int
) -> ExtractResult:
    """Extract one page (1-based). Mirrors the original ``extract_specific_page`` script."""
    return extract_pages(input_pdf_path, output_pdf_path, [page_number])
