"""Tests for pydeef.core.

PDFs are generated on the fly (see helpers.py): each page gets a unique width,
so tests can tell exactly which pages ended up where - no fixtures to commit.

Run with either:
    pytest
    python -m unittest discover -s tests -v
"""

import unittest
from pathlib import Path

from helpers import TempDirTestCase, make_pdf, widths
from pydeef.core import (
    PydeefError,
    count_pages,
    extract_pages,
    extract_specific_page,
    merge_pdfs,
    open_pdf,
    parse_page_spec,
    with_pdf_suffix,
)


class ParsePageSpecTests(unittest.TestCase):
    def test_single_page(self):
        self.assertEqual(parse_page_spec("13", 20), [13])

    def test_lists_and_ranges(self):
        self.assertEqual(parse_page_spec("1-3, 5, 8-10", 20), [1, 2, 3, 5, 8, 9, 10])

    def test_open_ended_range(self):
        self.assertEqual(parse_page_spec("18-", 20), [18, 19, 20])

    def test_keeps_order_and_drops_duplicates(self):
        self.assertEqual(parse_page_spec("3,1,3,2-3", 5), [3, 1, 2])

    def test_semicolons_spaces_and_trailing_comma(self):
        self.assertEqual(parse_page_spec(" 2 ; 4 , ", 5), [2, 4])

    def test_last_page_is_allowed(self):
        self.assertEqual(parse_page_spec("20", 20), [20])

    def test_invalid_specs_raise(self):
        for bad in ["", "   ", ",", "abc", "0", "21", "5-3", "1--2", "-3", "1-2-3", "\u00b2", "1.5"]:
            with self.subTest(spec=bad):
                with self.assertRaises(PydeefError):
                    parse_page_spec(bad, 20)

    def test_empty_document_raises(self):
        with self.assertRaises(PydeefError):
            parse_page_spec("1", 0)


class HelperTests(unittest.TestCase):
    def test_with_pdf_suffix(self):
        self.assertEqual(with_pdf_suffix("a"), Path("a.pdf"))
        self.assertEqual(with_pdf_suffix("a.PDF"), Path("a.PDF"))
        self.assertEqual(with_pdf_suffix("a.v2"), Path("a.v2.pdf"))


class OpenPdfTests(TempDirTestCase):
    def test_missing_file(self):
        with self.assertRaises(PydeefError) as ctx:
            open_pdf(self.dir / "nope.pdf")
        self.assertIn("not found", str(ctx.exception).lower())

    def test_not_a_pdf(self):
        fake = self.dir / "fake.pdf"
        fake.write_text("this is definitely not a pdf")
        with self.assertRaises(PydeefError):
            open_pdf(fake)

    def test_empty_file(self):
        empty = self.dir / "empty.pdf"
        empty.write_bytes(b"")
        with self.assertRaises(PydeefError):
            open_pdf(empty)

    def test_password_protected(self):
        locked = make_pdf(self.dir / "locked.pdf", 100, user_password="secret")
        with self.assertRaises(PydeefError) as ctx:
            open_pdf(locked)
        self.assertIn("password", str(ctx.exception).lower())

    def test_empty_user_password_opens_transparently(self):
        pdf = make_pdf(self.dir / "owner_only.pdf", 100, 2, user_password="", owner_password="owner")
        self.assertEqual(count_pages(pdf), 2)

    def test_count_pages(self):
        self.assertEqual(count_pages(make_pdf(self.dir / "a.pdf", 100, 4)), 4)


class MergeTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.a = make_pdf(self.dir / "a.pdf", 100, 2)  # widths 100, 101
        self.b = make_pdf(self.dir / "b.pdf", 200, 3)  # widths 200, 201, 202
        self.c = make_pdf(self.dir / "c.pdf", 300, 1)  # width 300

    def test_merges_in_the_given_order(self):
        out = self.dir / "merged.pdf"
        result = merge_pdfs([self.b, self.a, self.c], out)
        self.assertEqual(widths(out), [200, 201, 202, 100, 101, 300])
        self.assertEqual((result.files, result.pages, result.output), (3, 6, out))
        self.assertIsNone(result.deleted)
        self.assertEqual(result.warnings, [])

    def test_adds_pdf_extension_when_missing(self):
        result = merge_pdfs([self.a, self.b], self.dir / "combined")
        self.assertEqual(result.output, self.dir / "combined.pdf")
        self.assertTrue(result.output.is_file())

    def test_needs_at_least_two_files(self):
        with self.assertRaises(PydeefError):
            merge_pdfs([self.a], self.dir / "x.pdf")
        with self.assertRaises(PydeefError):
            merge_pdfs([], self.dir / "x.pdf")

    def test_needs_an_output_path(self):
        with self.assertRaises(PydeefError):
            merge_pdfs([self.a, self.b], "  ")

    def test_progress_callback(self):
        calls = []
        merge_pdfs([self.a, self.b, self.c], self.dir / "m.pdf", progress=lambda d, t: calls.append((d, t)))
        self.assertEqual(calls, [(1, 3), (2, 3), (3, 3)])

    def test_replaces_an_existing_output(self):
        out = self.dir / "merged.pdf"
        out.write_text("old content")
        merge_pdfs([self.a, self.b], out)
        self.assertEqual(widths(out), [100, 101, 200, 201, 202])

    def test_failed_merge_keeps_existing_output_and_leaves_no_temp_files(self):
        out = self.dir / "merged.pdf"
        out.write_bytes(b"precious")
        broken = self.dir / "broken.pdf"
        broken.write_text("not a pdf")
        with self.assertRaises(PydeefError):
            merge_pdfs([self.a, broken], out)
        self.assertEqual(out.read_bytes(), b"precious")
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])
        self.assertEqual([p.name for p in self.dir.glob(".*.tmp")], [])

    def test_missing_input_is_reported(self):
        with self.assertRaises(PydeefError) as ctx:
            merge_pdfs([self.a, self.dir / "ghost.pdf"], self.dir / "m.pdf")
        self.assertIn("ghost.pdf", str(ctx.exception))

    def test_missing_output_folder(self):
        with self.assertRaises(PydeefError):
            merge_pdfs([self.a, self.b], self.dir / "no_such_folder" / "m.pdf")

    def test_sources_are_not_modified(self):
        before = self.a.read_bytes(), self.b.read_bytes()
        merge_pdfs([self.a, self.b], self.dir / "m.pdf")
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), before)

    def test_can_overwrite_one_of_the_inputs(self):
        merge_pdfs([self.a, self.b], self.a)
        self.assertEqual(widths(self.a), [100, 101, 200, 201, 202])

    # --- the "delete the old merged file" behaviour of the original script ---
    def test_deletes_old_file_after_success(self):
        old = self.dir / "merged_pdfs.pdf"
        make_pdf(old, 500)
        result = merge_pdfs([self.a, self.b], self.dir / "pds-updated.pdf", delete_old=old)
        self.assertFalse(old.exists())
        self.assertEqual(result.deleted, old)
        self.assertTrue((self.dir / "pds-updated.pdf").is_file())

    def test_old_file_survives_when_the_merge_fails(self):
        old = self.dir / "merged_pdfs.pdf"
        make_pdf(old, 500)
        with self.assertRaises(PydeefError):
            merge_pdfs([self.a, self.dir / "ghost.pdf"], self.dir / "m.pdf", delete_old=old)
        self.assertTrue(old.exists())

    def test_old_file_not_found_is_only_a_warning(self):
        result = merge_pdfs([self.a, self.b], self.dir / "m.pdf", delete_old=self.dir / "gone.pdf")
        self.assertTrue((self.dir / "m.pdf").is_file())
        self.assertIsNone(result.deleted)
        self.assertEqual(len(result.warnings), 1)

    def test_old_file_equal_to_output_is_replaced_not_deleted(self):
        out = self.dir / "merged_pdfs.pdf"
        make_pdf(out, 500)
        result = merge_pdfs([self.a, self.b], out, delete_old=out)
        self.assertTrue(out.is_file())
        self.assertEqual(widths(out), [100, 101, 200, 201, 202])
        self.assertIsNone(result.deleted)
        self.assertEqual(len(result.warnings), 1)


class ExtractTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.src = make_pdf(self.dir / "book.pdf", 100, 15)  # widths 100..114

    def test_single_page(self):
        out = self.dir / "worksheet.pdf"
        result = extract_pages(self.src, out, "13")
        self.assertEqual(widths(out), [112])  # page 13 -> index 12 -> 100 + 12
        self.assertEqual(result.pages, [13])
        self.assertEqual(result.source_pages, 15)

    def test_ranges_and_order(self):
        out = self.dir / "picked.pdf"
        extract_pages(self.src, out, "5, 1-2, 14-")
        self.assertEqual(widths(out), [104, 100, 101, 113, 114])

    def test_accepts_a_list_of_numbers(self):
        out = self.dir / "list.pdf"
        extract_pages(self.src, out, [2, 1, 2])
        self.assertEqual(widths(out), [101, 100])

    def test_original_function_name_still_works(self):
        out = self.dir / "one.pdf"
        result = extract_specific_page(self.src, out, 13)
        self.assertEqual(widths(out), [112])
        self.assertEqual(result.pages, [13])

    def test_page_out_of_range(self):
        with self.assertRaises(PydeefError) as ctx:
            extract_pages(self.src, self.dir / "x.pdf", "16")
        self.assertIn("15", str(ctx.exception))
        self.assertFalse((self.dir / "x.pdf").exists())

    def test_invalid_numbers_in_a_list(self):
        for bad in ([0], [16], [], [True], ["3"]):
            with self.subTest(pages=bad):
                with self.assertRaises(PydeefError):
                    extract_pages(self.src, self.dir / "x.pdf", bad)

    def test_refuses_to_overwrite_the_source(self):
        before = self.src.read_bytes()
        with self.assertRaises(PydeefError):
            extract_pages(self.src, self.src, "1")
        self.assertEqual(self.src.read_bytes(), before)

    def test_adds_pdf_extension(self):
        result = extract_pages(self.src, self.dir / "page13", "13")
        self.assertEqual(result.output, self.dir / "page13.pdf")
        self.assertTrue(result.output.is_file())

    def test_missing_source(self):
        with self.assertRaises(PydeefError):
            extract_pages(self.dir / "ghost.pdf", self.dir / "x.pdf", "1")

    def test_replaces_an_existing_output(self):
        out = self.dir / "o.pdf"
        out.write_text("old")
        extract_pages(self.src, out, "1")
        self.assertEqual(widths(out), [100])

    def test_no_temp_files_left_behind(self):
        extract_pages(self.src, self.dir / "o.pdf", "1-3")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["book.pdf", "o.pdf"])


if __name__ == "__main__":
    unittest.main()
