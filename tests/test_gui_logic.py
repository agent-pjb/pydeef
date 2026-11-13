"""Headless tests for the GUI *logic* in pydeef.gui.

Tk itself is swapped for tiny stand-ins, so these tests run anywhere (CI
included, no display needed) and check our own code: list handling, input
validation, background threads and the dialogs that get shown.

They deliberately do NOT check how the window looks - launch the app for that.
"""

import base64
import struct
import sys
import time
import types
import unittest
from unittest import mock
from unittest.mock import MagicMock

from helpers import TempDirTestCase, make_pdf, widths

# --------------------------------------------------------------------------- #
# Stand-ins for tkinter
# --------------------------------------------------------------------------- #
DIALOGS = []  # every messagebox / filedialog call: (kind, args, kwargs)


class FakeTclError(Exception):
    pass


class FakeVar:
    def __init__(self, master=None, value="", name=None):
        self._value = value
        self._callbacks = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for callback in list(self._callbacks):
            callback("var", "", "write")

    def trace_add(self, mode, callback):
        self._callbacks.append(callback)


class FakeTree:
    """The bits of ttk.Treeview that pydeef uses, backed by a plain list."""

    def __init__(self, master=None, columns=(), **kwargs):
        self.columns = list(columns)
        self.rows = []
        self.data = {}
        self.selected = []

    def heading(self, *args, **kwargs): ...
    def column(self, *args, **kwargs): ...
    def grid(self, *args, **kwargs): ...
    def configure(self, *args, **kwargs): ...
    def bind(self, *args, **kwargs): ...
    def yview(self, *args, **kwargs): ...
    def see(self, row_id): ...

    def insert(self, parent, index, iid=None, values=()):
        assert iid not in self.data, "duplicate row id"
        self.rows.append(iid)
        self.data[iid] = list(values)

    def get_children(self):
        return tuple(self.rows)

    def set(self, row_id, column, value):
        self.data[row_id][self.columns.index(column)] = value

    def selection(self):
        return tuple(self.selected)

    def delete(self, row_id):
        self.rows.remove(row_id)
        del self.data[row_id]
        self.selected = [row for row in self.selected if row != row_id]

    def index(self, row_id):
        return self.rows.index(row_id)

    def move(self, row_id, parent, index):
        self.rows.remove(row_id)
        self.rows.insert(index, row_id)

    # convenience for assertions
    def names(self):
        return [self.data[row][1] for row in self.rows]


class FakeRoot:
    """A root window whose ``after`` callbacks are run by ``pump()``."""

    def __init__(self):
        self.scheduled = []
        self.tk = MagicMock()
        self.tk.splitlist = lambda text: text.split("|")

    def __getattr__(self, name):  # title(), geometry(), bind(), configure(), ...
        attr = MagicMock()
        if name == "winfo_fpixels":
            attr.return_value = 96.0
        return attr

    def after(self, delay, callback, *args):
        self.scheduled.append((callback, args))

    def pump(self, timeout=10.0):
        deadline = time.time() + timeout
        while self.scheduled:
            if time.time() > deadline:
                raise RuntimeError("background task never finished")
            callback, args = self.scheduled.pop(0)
            callback(*args)
            time.sleep(0.002)


def _recorder(kind, result=None):
    def record(*args, **kwargs):
        DIALOGS.append((kind, args, kwargs))
        return result

    return record


def _build_stub_modules():
    tk = types.ModuleType("tkinter")
    tk.TclError = FakeTclError
    tk.StringVar = tk.BooleanVar = FakeVar
    tk.Tk = MagicMock
    tk.Misc = object
    tk.PhotoImage = lambda *a, **k: MagicMock()
    tk.Menu = lambda *a, **k: MagicMock()

    ttk = types.ModuleType("tkinter.ttk")
    for name in (
        "Frame", "Label", "Button", "Entry", "Checkbutton", "Notebook",
        "Progressbar", "Separator", "Scrollbar", "Style",
    ):  # fmt: skip
        setattr(ttk, name, lambda *a, **k: MagicMock())
    ttk.Treeview = FakeTree

    messagebox = types.ModuleType("tkinter.messagebox")
    for name in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, name, _recorder(name))
    messagebox.askyesno = _recorder("askyesno", True)

    filedialog = types.ModuleType("tkinter.filedialog")
    filedialog.askopenfilenames = _recorder("askopenfilenames", ())
    filedialog.askopenfilename = _recorder("askopenfilename", "")
    filedialog.asksaveasfilename = _recorder("asksaveasfilename", "")

    font = types.ModuleType("tkinter.font")
    font.families = lambda *a, **k: ["DejaVu Sans"]
    font.nametofont = lambda *a, **k: MagicMock(actual=lambda *x: "DejaVu Sans")

    tk.ttk, tk.messagebox, tk.filedialog, tk.font = ttk, messagebox, filedialog, font
    return {
        "tkinter": tk,
        "tkinter.ttk": ttk,
        "tkinter.messagebox": messagebox,
        "tkinter.filedialog": filedialog,
        "tkinter.font": font,
    }


gui = None
_patcher = None


def setUpModule():
    global gui, _patcher
    _patcher = mock.patch.dict(sys.modules, _build_stub_modules())
    _patcher.start()
    sys.modules.pop("pydeef.gui", None)
    import pydeef.gui as gui_module  # imported against the stand-ins

    gui = gui_module


def tearDownModule():
    _patcher.stop()  # restores sys.modules, dropping the stub-backed pydeef.gui


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
class GuiTestCase(TempDirTestCase):
    def setUp(self):
        super().setUp()
        DIALOGS.clear()
        self.root = FakeRoot()
        self.app = gui.PydeefApp(self.root, dnd_enabled=False)
        self.tree = self.app.merge_tree

    def last(self, kind):
        return [call for call in DIALOGS if call[0] == kind][-1]

    def dialog_text(self, kind):
        return " ".join(str(arg) for arg in self.last(kind)[1])

    def add_three(self):
        self.a = make_pdf(self.dir / "a.pdf", 100, 2)
        self.b = make_pdf(self.dir / "b.pdf", 200, 3)
        self.c = make_pdf(self.dir / "c.pdf", 300, 1)
        self.app._add_merge_paths([str(self.a), str(self.b), str(self.c)])
        return list(self.tree.rows)


class MergeTabTests(GuiTestCase):
    def test_starts_empty(self):
        self.assertEqual(self.app.merge_summary.get(), "No files added yet")

    def test_adding_files_skips_bad_ones_and_suggests_an_output_name(self):
        notes = self.dir / "notes.txt"
        notes.write_text("hello")
        broken = self.dir / "broken.pdf"
        broken.write_text("garbage")
        locked = make_pdf(self.dir / "locked.pdf", 400, user_password="pw")
        self.add_three()
        self.app._add_merge_paths([str(notes), str(broken), str(locked)])

        self.assertEqual(self.tree.names(), ["a.pdf", "b.pdf", "c.pdf"])
        self.assertEqual([self.tree.data[r][0] for r in self.tree.rows], [1, 2, 3])
        self.assertEqual(self.app.merge_summary.get(), "3 files · 6 pages in total")
        self.assertEqual(self.app.merge_output.get(), str(self.dir / "merged.pdf"))
        warning = self.dialog_text("showwarning")
        for expected in ("notes.txt", "broken.pdf", "password"):
            self.assertIn(expected, warning)

    def test_dropping_a_folder_adds_its_pdfs_sorted_by_name(self):
        folder = self.dir / "folder"
        folder.mkdir()
        make_pdf(folder / "z.pdf", 500)
        make_pdf(folder / "m.pdf", 600)
        (folder / "readme.txt").write_text("ignored")
        self.app._add_merge_paths([str(folder)])
        self.assertEqual(self.tree.names(), ["m.pdf", "z.pdf"])

    def test_remove_and_clear(self):
        ids = self.add_three()
        self.tree.selected = [ids[0], ids[2]]
        self.app._remove_selected()
        self.assertEqual(self.tree.names(), ["b.pdf"])
        self.app._clear_merge_list()
        self.assertEqual(self.tree.rows, [])
        self.assertEqual(self.app.merge_summary.get(), "No files added yet")

    def test_reordering(self):
        a, b, c = self.add_three()
        self.tree.selected = [c]
        self.app._move_up()
        self.assertEqual(self.tree.rows, [a, c, b])

        self.tree.selected = [a, c]  # a block already at the top stays put
        self.app._move_up()
        self.assertEqual(self.tree.rows, [a, c, b])

        self.tree.selected = [c, b]  # a block already at the bottom stays put
        self.app._move_down()
        self.assertEqual(self.tree.rows, [a, c, b])

        self.tree.selected = [a]
        self.app._move_down()
        self.assertEqual(self.tree.rows, [c, a, b])

        self.tree.selected = [c, a]  # several rows move together
        self.app._move_down()
        self.assertEqual(self.tree.rows, [b, c, a])
        self.assertEqual([self.tree.data[r][0] for r in self.tree.rows], [1, 2, 3])  # renumbered

    def test_merge_runs_in_the_background_and_reports(self):
        a, b, c = self.add_three()
        self.tree.selected = [a, c]
        self.app._move_down()  # c is already last, so only a moves: b, a, c
        self.assertEqual(self.tree.rows, [b, a, c])
        output = self.dir / "result.pdf"
        self.app.merge_output.set(str(output))

        self.app._on_merge()
        self.root.pump()

        self.assertFalse(self.app._busy)
        self.assertEqual(widths(output), [200, 201, 202, 100, 101, 300])
        self.assertEqual(self.last("showinfo")[1][0], "Merge complete")
        self.assertIn("6 pages", self.dialog_text("showinfo"))

    def test_merge_can_delete_the_old_file(self):
        self.add_three()
        old = make_pdf(self.dir / "merged_pdfs.pdf", 900)
        self.app.delete_old_enabled.set(True)
        self.app.delete_old_path.set(str(old))
        self.app.merge_output.set(str(self.dir / "pds-updated.pdf"))

        self.app._on_merge()
        self.root.pump()

        self.assertFalse(old.exists())
        self.assertTrue((self.dir / "pds-updated.pdf").exists())
        self.assertIn("Deleted the old file", self.dialog_text("showinfo"))

    def test_declining_the_delete_confirmation_cancels_everything(self):
        self.add_three()
        old = make_pdf(self.dir / "merged_pdfs.pdf", 900)
        self.app.delete_old_enabled.set(True)
        self.app.delete_old_path.set(str(old))
        self.app.merge_output.set(str(self.dir / "out.pdf"))
        with mock.patch.object(gui.messagebox, "askyesno", return_value=False):
            self.app._on_merge()
            self.root.pump()
        self.assertTrue(old.exists())
        self.assertFalse((self.dir / "out.pdf").exists())

    def test_merge_errors_are_shown_and_the_ui_recovers(self):
        self.add_three()
        ghost = self.dir / "ghost.pdf"
        self.tree.insert("", "end", iid="ghost", values=(4, "ghost.pdf", 1, str(self.dir)))
        self.app._merge_items["ghost"] = (ghost, 1)
        self.app._on_merge()
        self.root.pump()
        self.assertFalse(self.app._busy)
        self.assertIn("ghost.pdf", self.dialog_text("showerror"))

    def test_merge_needs_two_files(self):
        self.app._on_merge()
        self.assertEqual(self.last("showwarning")[1][0], "Not enough files")

    def test_unexpected_exceptions_are_shown_not_swallowed(self):
        self.app._run_task(lambda progress: 1 / 0, lambda result: None, "working")
        self.root.pump()
        self.assertIn("ZeroDivisionError", self.dialog_text("showerror"))
        self.assertFalse(self.app._busy)


class ExtractTabTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.book = make_pdf(self.dir / "book.pdf", 100, 15)
        self.app.extract_input.set(str(self.book))
        self.app._load_extract_input(str(self.book))

    def hint_style(self):
        return self.app.extract_hint_label.configure.call_args.kwargs["style"]

    def test_reads_the_page_count_and_suggests_an_output_name(self):
        self.assertEqual(self.app.extract_info.get(), "book.pdf · 15 pages")
        self.assertEqual(self.app.extract_output.get(), str(self.dir / "book_extracted.pdf"))

    def test_live_hint_validates_the_page_selection(self):
        self.app.extract_spec.set("2-3, 15")
        self.assertEqual(self.app.extract_hint.get(), "3 pages selected: 2, 3, 15")
        self.assertEqual(self.hint_style(), "Ok.TLabel")

        self.app.extract_spec.set("99")
        self.assertIn("15 pages", self.app.extract_hint.get())
        self.assertEqual(self.hint_style(), "Error.TLabel")

    def test_extracts_in_the_background(self):
        self.app.extract_spec.set("13")
        self.app._on_extract()
        self.root.pump()
        self.assertEqual(widths(self.dir / "book_extracted.pdf"), [112])
        self.assertEqual(self.last("showinfo")[1][0], "Extraction complete")

    def test_refuses_to_overwrite_the_source_pdf(self):
        before = self.book.read_bytes()
        self.app.extract_spec.set("1")
        self.app.extract_output.set(str(self.book))
        self.app._on_extract()
        self.root.pump()
        self.assertIn("same as the source", self.dialog_text("showerror"))
        self.assertEqual(self.book.read_bytes(), before)

    def test_asks_for_the_pages_when_missing(self):
        self.app.extract_spec.set("")
        self.app._on_extract()
        self.assertEqual(self.last("showwarning")[1][0], "Choose pages")

    def test_bad_and_cleared_inputs(self):
        self.app._load_extract_input(str(self.dir / "nope.pdf"))
        self.assertIn("not found", self.app.extract_info.get().lower())
        self.app._load_extract_input("")
        self.assertEqual(self.app.extract_info.get(), "Choose a PDF to begin.")


class BundledImageTests(unittest.TestCase):
    """The logo/icon files must exist, be real images, and load robustly."""

    PNG, GIF = b"\x89PNG\r\n\x1a\n", b"GIF8"

    def test_every_bundled_image_exists_and_has_the_right_format(self):
        for name in gui.BUNDLED_IMAGES:
            with self.subTest(image=name):
                path = gui.asset_path(name)
                self.assertTrue(path.is_file(), f"missing {path}")
                head = path.read_bytes()[:8]
                expected = self.GIF if name.endswith(".gif") else self.PNG
                self.assertTrue(head.startswith(expected), f"{name} is not a real {expected!r} file")

    def test_ico_uses_bmp_frames_that_every_tk_build_can_read(self):
        data = gui.asset_path("icon.ico").read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", data, 0)
        self.assertEqual((reserved, kind), (0, 1))
        sizes = set()
        for index in range(count):
            width, height, _c, _r, _p, _b, _size, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
            sizes.add(width or 256)
            self.assertFalse(data[offset:offset + 8] == self.PNG, "PNG-compressed frame in icon.ico")
            self.assertEqual(struct.unpack_from("<I", data, offset)[0], 40, "frame is not a BMP DIB")
        self.assertTrue({16, 32, 256} <= sizes)

    def test_load_photo_hands_tk_the_bytes_not_a_path(self):
        master = object()
        with mock.patch.object(gui.tk, "PhotoImage") as photo_image:
            gui.load_photo(master, "icon-64.png")
        kwargs = photo_image.call_args.kwargs
        self.assertIs(kwargs["master"], master)
        self.assertNotIn("file", kwargs)
        self.assertEqual(base64.b64decode(kwargs["data"]), gui.asset_path("icon-64.png").read_bytes())

    def test_load_first_photo_falls_back_and_logs_why(self):
        sentinel = object()
        failure = gui.tk.TclError("couldn't recognize image data")
        with mock.patch.object(gui, "load_photo", side_effect=[failure, sentinel]):
            with self.assertLogs("pydeef", level="WARNING") as logs:
                result = gui.load_first_photo(object(), ("a.png", "b.gif"))
        self.assertIs(result, sentinel)
        self.assertIn("a.png", logs.output[0])

    def test_load_first_photo_returns_none_when_everything_fails(self):
        with mock.patch.object(gui, "load_photo", side_effect=OSError("missing")):
            with self.assertLogs("pydeef", level="WARNING"):
                self.assertIsNone(gui.load_first_photo(object(), ("a.png", "b.gif")))

    def test_the_app_still_starts_and_uses_the_gif_when_png_cannot_be_read(self):
        gif_logo = MagicMock(name="gif-logo")

        def fake_load(master, name):
            if name.endswith(".png"):
                raise gui.tk.TclError("couldn't recognize data in image file")
            return gif_logo

        DIALOGS.clear()
        with mock.patch.object(gui, "load_photo", side_effect=fake_load):
            with self.assertLogs("pydeef", level="WARNING"):
                app = gui.PydeefApp(FakeRoot(), dnd_enabled=False)
        self.assertIn(gif_logo, app._images)


if __name__ == "__main__":
    unittest.main()
