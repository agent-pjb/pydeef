"""Tkinter user interface for pydeef.

The interface is deliberately thin: every PDF operation lives in
:mod:`pydeef.core`, and long-running work is executed on a background thread so
the window never freezes.
"""

from __future__ import annotations

import base64
import logging
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import __version__
from .core import (
    ExtractResult,
    MergeResult,
    PydeefError,
    count_pages,
    extract_pages,
    merge_pdfs,
    parse_page_spec,
    with_pdf_suffix,
)

try:  # Optional: drag & drop support. The app works fine without it.
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # ImportError, or a broken tkdnd binary on exotic platforms
    DND_FILES = None
    TkinterDnD = None

APP_NAME = "pydeef"
log = logging.getLogger("pydeef")
PDF_FILETYPES = [("PDF files", "*.pdf"), ("All files", "*.*")]
IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"


# --------------------------------------------------------------------------- #
# Theme (colours picked from the logo: deep navy, electric blue, signal red)
# --------------------------------------------------------------------------- #
class Palette:
    bg = "#070b1a"
    panel = "#0f1633"
    panel_alt = "#18214a"
    panel_hover = "#222d63"
    border = "#27316b"
    fg = "#e9edff"
    muted = "#8e98cc"
    blue = "#2f6bff"
    blue_hover = "#5a8bff"
    blue_pressed = "#2457d6"
    red = "#ff3b30"
    ok = "#3ddc97"
    error = "#ff7a7a"


def asset_path(name: str) -> Path:
    """Path to a bundled asset (works from source, when installed, and in PyInstaller)."""
    return Path(__file__).resolve().parent / "assets" / name


# Images bundled in src/pydeef/assets (used by the window and by --diagnose)
HEADER_LOGO_CANDIDATES = ("icon-64.png", "header-logo.gif")  # PNG first, GIF for very old Tk
WINDOW_ICON_FILES = ("icon-256.png", "icon-64.png", "icon-32.png", "icon-16.png")
BUNDLED_IMAGES = tuple(dict.fromkeys(HEADER_LOGO_CANDIDATES + WINDOW_ICON_FILES))


def load_photo(master: tk.Misc, name: str) -> tk.PhotoImage:
    """Load a bundled image as a Tk PhotoImage.

    The file is read in Python and handed to Tk as data instead of as a path.
    That avoids file-path encoding problems some Tk builds have (for example a
    Windows user folder containing accented characters).
    """
    raw = asset_path(name).read_bytes()  # OSError if the file is missing
    return tk.PhotoImage(master=master, data=base64.b64encode(raw).decode("ascii"))


def load_first_photo(master: tk.Misc, names: Sequence[str]) -> Optional[tk.PhotoImage]:
    """Try each image in turn; log why one failed instead of failing silently."""
    for name in names:
        try:
            return load_photo(master, name)
        except (tk.TclError, OSError) as exc:
            log.warning("pydeef: could not load image %s (%s)", name, exc)
    return None


def _pick_font_family() -> str:
    available = set(tkfont.families())
    for name in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Ubuntu", "Cantarell", "DejaVu Sans"):
        if name in available:
            return name
    return tkfont.nametofont("TkDefaultFont").actual("family")


def apply_theme(root: tk.Misc) -> None:
    """Style ttk widgets with the pydeef dark theme."""
    p = Palette
    family = _pick_font_family()
    scale = max(1.0, root.winfo_fpixels("1i") / 96.0)  # HiDPI-friendly row heights

    for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        tkfont.nametofont(font_name).configure(family=family, size=10)

    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=p.bg)

    style.configure(
        ".",
        background=p.bg,
        foreground=p.fg,
        fieldbackground=p.panel,
        bordercolor=p.border,
        lightcolor=p.border,
        darkcolor=p.border,
        troughcolor=p.panel,
        focuscolor=p.bg,
        font=(family, 10),
    )

    # Labels
    style.configure("TLabel", background=p.bg, foreground=p.fg)
    style.configure("Title.TLabel", font=(family, 22, "bold"))
    style.configure("Subtitle.TLabel", foreground=p.muted)
    style.configure("Section.TLabel", font=(family, 10, "bold"))
    style.configure("Muted.TLabel", foreground=p.muted)
    style.configure("Ok.TLabel", foreground=p.ok)
    style.configure("Error.TLabel", foreground=p.error)
    style.configure("Hint.TLabel", background=p.panel, foreground=p.muted, font=(family, 11))

    # Buttons
    style.configure(
        "TButton",
        background=p.panel_alt,
        foreground=p.fg,
        bordercolor=p.border,
        focuscolor=p.panel_alt,
        padding=(14, 7),
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("disabled", p.panel), ("pressed", p.border), ("active", p.panel_hover)],
        foreground=[("disabled", p.muted)],
    )
    style.configure(
        "Accent.TButton",
        background=p.blue,
        foreground="#ffffff",
        bordercolor=p.blue,
        focuscolor=p.blue,
        padding=(26, 10),
        font=(family, 11, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", p.panel_alt), ("pressed", p.blue_pressed), ("active", p.blue_hover)],
        foreground=[("disabled", p.muted)],
    )
    style.configure("Danger.TButton", foreground="#ff9d96")
    style.map("Danger.TButton", background=[("active", "#3a1d33"), ("pressed", "#4a2038")])

    # Inputs
    style.configure(
        "TEntry",
        fieldbackground=p.panel,
        foreground=p.fg,
        insertcolor=p.fg,
        bordercolor=p.border,
        lightcolor=p.border,
        darkcolor=p.border,
        padding=7,
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", p.bg)],
        foreground=[("disabled", p.muted)],
        bordercolor=[("focus", p.blue)],
        lightcolor=[("focus", p.blue)],
        darkcolor=[("focus", p.blue)],
    )
    style.configure("TCheckbutton", background=p.bg, foreground=p.fg, indicatorcolor=p.panel)
    style.map(
        "TCheckbutton",
        background=[("active", p.bg)],
        foreground=[("disabled", p.muted)],
        indicatorcolor=[("selected", p.blue), ("pressed", p.blue_hover)],
    )

    # Tabs
    style.configure("TNotebook", background=p.bg, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=p.panel,
        foreground=p.muted,
        padding=(24, 10),
        borderwidth=0,
        font=(family, 10, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", p.panel_alt), ("active", p.panel_hover)],
        foreground=[("selected", p.fg)],
    )

    # File list
    style.configure(
        "Treeview",
        background=p.panel,
        fieldbackground=p.panel,
        foreground=p.fg,
        bordercolor=p.border,
        borderwidth=1,
        rowheight=int(30 * scale),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", p.blue)],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Treeview.Heading",
        background=p.panel_alt,
        foreground=p.muted,
        relief="flat",
        padding=(8, 6),
        font=(family, 9, "bold"),
    )
    style.map("Treeview.Heading", background=[("active", p.panel_hover)])

    style.configure(
        "Vertical.TScrollbar",
        background=p.panel_alt,
        troughcolor=p.panel,
        bordercolor=p.panel,
        arrowcolor=p.muted,
        lightcolor=p.panel_alt,
        darkcolor=p.panel_alt,
    )
    style.map("Vertical.TScrollbar", background=[("active", p.panel_hover)])

    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=p.panel,
        background=p.blue,
        bordercolor=p.panel,
        lightcolor=p.blue,
        darkcolor=p.blue,
    )
    style.configure("TSeparator", background=p.border)


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def reveal_in_file_manager(path: Path) -> None:
    """Open the system file manager with ``path`` selected (best effort)."""
    try:
        if IS_WINDOWS:
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif IS_MAC:
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except Exception:
        pass


def summarize_pages(pages: Sequence[int], limit: int = 12) -> str:
    shown = ", ".join(str(number) for number in pages[:limit])
    extra = len(pages) - limit
    return shown if extra <= 0 else f"{shown} … (+{extra} more)"


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _prepare_platform() -> None:
    """Windows: crisp text on HiDPI screens and the right taskbar icon."""
    if not IS_WINDOWS:
        return
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pydeef.app")
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def create_root() -> Tuple[tk.Tk, bool]:
    """Create the Tk root; returns ``(root, drag_and_drop_available)``."""
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk(), True
        except Exception:
            pass
    return tk.Tk(), False


# --------------------------------------------------------------------------- #
# The application
# --------------------------------------------------------------------------- #
class PydeefApp:
    def __init__(self, root: tk.Tk, dnd_enabled: bool) -> None:
        self.root = root
        self.dnd = bool(dnd_enabled and DND_FILES is not None)
        self._busy = False
        self._images: List[Any] = []  # keep PhotoImage references alive
        self._last_dir = Path.home()

        # Merge tab state
        self._merge_items: Dict[str, Tuple[Path, int]] = {}  # row id -> (path, pages)
        self._merge_counter = 0
        self._merge_auto_output = ""

        # Extract tab state
        self._extract_total: Optional[int] = None
        self._extract_auto_output = ""
        self._extract_loaded = ""  # the path whose page count is currently shown

        # Shared variables
        self.status = tk.StringVar(value="Ready")
        self.reveal_when_done = tk.BooleanVar(value=False)

        root.title("pydeef - merge PDFs & extract pages")
        root.geometry("920x700")
        root.minsize(820, 640)

        apply_theme(root)
        self._set_window_icon()
        self._build_menu()
        self._build_header()
        self._build_statusbar()
        self._build_tabs()
        self._bind_shortcuts()
        self._refresh_merge_list()
        self._update_extract_hint()

    # ------------------------------------------------------------------ #
    # Window chrome
    # ------------------------------------------------------------------ #
    def _set_window_icon(self) -> None:
        if IS_WINDOWS:  # classic .ico: used for the title bar / taskbar when Tk accepts it
            try:
                self.root.iconbitmap(default=str(asset_path("icon.ico")))
            except tk.TclError as exc:
                log.warning("pydeef: could not set the .ico window icon (%s)", exc)

        # Several sizes, so the OS can pick a crisp one for the title bar, taskbar and Alt-Tab.
        photos = []
        for name in WINDOW_ICON_FILES:
            try:
                photos.append(load_photo(self.root, name))
            except (tk.TclError, OSError) as exc:
                log.warning("pydeef: could not load window icon %s (%s)", name, exc)
        if photos:
            try:
                self.root.iconphoto(True, *photos)
                self._images.extend(photos)
            except tk.TclError as exc:
                log.warning("pydeef: could not set the window icon (%s)", exc)

    def _build_menu(self) -> None:
        mod = "Cmd" if IS_MAC else "Ctrl"
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label="Add PDFs to merge…", accelerator=f"{mod}+O", command=self._browse_merge_files
        )
        file_menu.add_command(
            label="Choose PDF to extract from…", accelerator=f"{mod}+E", command=self._browse_extract_input
        )
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator=f"{mod}+Q", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label=f"About {APP_NAME}", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.configure(menu=menubar)

    def _bind_shortcuts(self) -> None:
        mod = "Command" if IS_MAC else "Control"
        self.root.bind(f"<{mod}-o>", lambda _e: self._browse_merge_files())
        self.root.bind(f"<{mod}-e>", lambda _e: self._browse_extract_input())
        self.root.bind(f"<{mod}-q>", lambda _e: self.root.destroy())
        self.merge_tree.bind("<Delete>", lambda _e: self._remove_selected())
        self.merge_tree.bind("<BackSpace>", lambda _e: self._remove_selected())

    def _show_about(self) -> None:
        dnd_line = "Drag & drop: enabled" if self.dnd else "Drag & drop: not available (pip install tkinterdnd2)"
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "Merge PDFs and extract pages - simple, fast and offline.\n"
            "Built with Python, Tkinter and pypdf.\n\n"
            f"{dnd_line}\n\nLicensed under the MIT License.",
            parent=self.root,
        )

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, padding=(26, 22, 26, 6))
        header.pack(fill="x")
        logo = load_first_photo(self.root, HEADER_LOGO_CANDIDATES)
        if logo is not None:
            self._images.append(logo)  # keep a reference, or Tk shows nothing
            ttk.Label(header, image=logo).pack(side="left", padx=(0, 16))
        text = ttk.Frame(header)
        text.pack(side="left")
        ttk.Label(text, text="pydeef", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            text,
            text="Merge PDFs and extract pages - fast, simple and offline.",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(26, 8, 26, 14))
        bar.pack(side="bottom", fill="x")
        ttk.Separator(self.root, orient="horizontal").pack(side="bottom", fill="x")

        ttk.Label(bar, textvariable=self.status, style="Muted.TLabel").pack(side="left")
        ttk.Checkbutton(bar, text="Show file in folder when done", variable=self.reveal_when_done).pack(
            side="right"
        )
        self.progress = ttk.Progressbar(bar, mode="determinate", length=170, maximum=100)
        self.progress.pack(side="right", padx=16)

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=26, pady=(10, 12))

        merge_tab = ttk.Frame(self.notebook, padding=20)
        extract_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(merge_tab, text="  Merge PDFs  ")
        self.notebook.add(extract_tab, text="  Extract pages  ")

        self._build_merge_tab(merge_tab)
        self._build_extract_tab(extract_tab)

        if self.dnd:
            self._register_drop(extract_tab, self._on_drop_extract)

    # ------------------------------------------------------------------ #
    # Shared widgets / helpers
    # ------------------------------------------------------------------ #
    def _path_field(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        command: Callable[[], Any],
        row: int,
    ) -> Tuple[ttk.Entry, ttk.Button]:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=label, style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=1, column=0, sticky="ew")
        button = ttk.Button(frame, text="Browse…", command=command)
        button.grid(row=1, column=1, padx=(8, 0))
        return entry, button

    def _register_drop(self, widget: Any, handler: Callable[[Any], Any]) -> None:
        if not self.dnd:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", handler)
        except Exception:
            pass

    def _dropped_paths(self, event: Any) -> List[str]:
        return list(self.root.tk.splitlist(event.data))

    def _ask_open_files(self, title: str) -> List[str]:
        chosen = filedialog.askopenfilenames(
            title=title, filetypes=PDF_FILETYPES, initialdir=str(self._last_dir), parent=self.root
        )
        if isinstance(chosen, str):  # some Tk builds return one big string
            chosen = self.root.tk.splitlist(chosen)
        return [str(item) for item in chosen]

    def _ask_open_file(self, title: str) -> str:
        chosen = filedialog.askopenfilename(
            title=title, filetypes=PDF_FILETYPES, initialdir=str(self._last_dir), parent=self.root
        )
        return str(chosen) if chosen else ""

    def _ask_save_file(self, title: str, initial: str) -> str:
        initial_path = Path(initial) if initial else None
        chosen = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".pdf",
            filetypes=PDF_FILETYPES,
            initialdir=str(initial_path.parent if initial_path else self._last_dir),
            initialfile=initial_path.name if initial_path else "",
            parent=self.root,
        )
        return str(chosen) if chosen else ""

    def _remember_dir(self, path: Path) -> None:
        folder = path if path.is_dir() else path.parent
        if folder.is_dir():
            self._last_dir = folder

    def _confirm_overwrite(self, path: Path) -> bool:
        if not path.exists():
            return True
        return messagebox.askyesno(
            "Replace existing file?",
            f"'{path.name}' already exists.\n\nDo you want to replace it?",
            icon="warning",
            parent=self.root,
        )

    # ------------------------------------------------------------------ #
    # Background work
    # ------------------------------------------------------------------ #
    def _set_busy(self, busy: bool, text: str = "", determinate: bool = True) -> None:
        self._busy = busy
        state = ["disabled"] if busy else ["!disabled"]
        self.merge_button.state(state)
        self.extract_button.state(state)
        if busy:
            self.status.set(text)
            if determinate:
                self.progress.configure(mode="determinate", value=0)
            else:
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)

    def _run_task(
        self,
        work: Callable[[Callable[[int, int], None]], Any],
        on_success: Callable[[Any], None],
        status_text: str,
        determinate: bool = True,
    ) -> None:
        """Run ``work(progress)`` on a thread; call ``on_success(result)`` on the UI thread."""
        self._set_busy(True, status_text, determinate)
        results: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()

        def worker() -> None:
            try:
                outcome = work(lambda done, total: results.put(("progress", done, total)))
            except Exception as exc:  # shown to the user by the UI thread
                results.put(("error", exc))
            else:
                results.put(("done", outcome))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_task(results, on_success, determinate)

    def _poll_task(
        self, results: "queue.Queue[Tuple[Any, ...]]", on_success: Callable[[Any], None], determinate: bool
    ) -> None:
        while True:
            try:
                message = results.get_nowait()
            except queue.Empty:
                self.root.after(40, self._poll_task, results, on_success, determinate)
                return
            kind = message[0]
            if kind == "progress":
                if determinate and message[2]:
                    self.progress.configure(value=message[1] * 100.0 / message[2])
            elif kind == "done":
                self._set_busy(False)
                on_success(message[1])
                return
            else:
                self._set_busy(False)
                self._show_error(message[1])
                return

    def _show_error(self, exc: BaseException) -> None:
        self.status.set("Something went wrong")
        if isinstance(exc, PydeefError):
            messagebox.showerror(APP_NAME, str(exc), parent=self.root)
        else:
            messagebox.showerror(
                APP_NAME, f"Unexpected error: {type(exc).__name__}: {exc}", parent=self.root
            )

    # ------------------------------------------------------------------ #
    # Merge tab
    # ------------------------------------------------------------------ #
    def _build_merge_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        ttk.Label(tab, text="Files to merge (top to bottom)", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )

        # File list + scrollbar
        list_frame = ttk.Frame(tab)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.merge_tree = ttk.Treeview(
            list_frame,
            columns=("order", "name", "pages", "folder"),
            show="headings",
            selectmode="extended",
            height=8,
        )
        for column, title, width, stretch, anchor in (
            ("order", "#", 46, False, "center"),
            ("name", "File", 260, True, "w"),
            ("pages", "Pages", 72, False, "center"),
            ("folder", "Folder", 260, True, "w"),
        ):
            self.merge_tree.heading(column, text=title)
            self.merge_tree.column(column, width=width, minwidth=40, stretch=stretch, anchor=anchor)
        self.merge_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.merge_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.merge_tree.configure(yscrollcommand=scrollbar.set)

        hint_text = (
            "Drag & drop PDF files here\nor click “Add files…”"
            if self.dnd
            else "Click “Add files…” to choose PDF files"
        )
        self.merge_hint = ttk.Label(self.merge_tree, text=hint_text, style="Hint.TLabel", justify="center")
        self.merge_hint.place(relx=0.5, rely=0.5, anchor="center")

        if self.dnd:
            self._register_drop(self.merge_tree, self._on_drop_merge)
            self._register_drop(self.merge_hint, self._on_drop_merge)

        # Buttons next to the list
        buttons = ttk.Frame(tab)
        buttons.grid(row=1, column=1, sticky="n", padx=(12, 0))
        for text, command, style in (
            ("Add files…", self._browse_merge_files, "TButton"),
            ("↑  Move up", self._move_up, "TButton"),
            ("↓  Move down", self._move_down, "TButton"),
            ("Remove", self._remove_selected, "Danger.TButton"),
            ("Clear all", self._clear_merge_list, "Danger.TButton"),
        ):
            ttk.Button(buttons, text=text, command=command, style=style).pack(fill="x", pady=3)

        self.merge_summary = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.merge_summary, style="Muted.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 12)
        )

        # Output
        self.merge_output = tk.StringVar()
        self._path_field(tab, "Save merged PDF as", self.merge_output, self._browse_merge_output, row=3)

        # Optional: delete the old merged file (behaviour of the original script)
        self.delete_old_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            tab,
            text="After a successful merge, delete an old merged file",
            variable=self.delete_old_enabled,
            command=self._toggle_delete_old,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.delete_old_path = tk.StringVar()
        frame = ttk.Frame(tab)
        frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        frame.columnconfigure(0, weight=1)
        self.delete_old_entry = ttk.Entry(frame, textvariable=self.delete_old_path)
        self.delete_old_entry.grid(row=0, column=0, sticky="ew")
        self.delete_old_button = ttk.Button(frame, text="Browse…", command=self._browse_delete_old)
        self.delete_old_button.grid(row=0, column=1, padx=(8, 0))
        self._toggle_delete_old()

        self.merge_button = ttk.Button(tab, text="Merge PDFs", style="Accent.TButton", command=self._on_merge)
        self.merge_button.grid(row=6, column=0, columnspan=2, sticky="e")

    def _toggle_delete_old(self) -> None:
        state = ["!disabled"] if self.delete_old_enabled.get() else ["disabled"]
        self.delete_old_entry.state(state)
        self.delete_old_button.state(state)

    def _browse_delete_old(self) -> None:
        chosen = self._ask_open_file("Choose the old merged file to delete")
        if chosen:
            self.delete_old_path.set(chosen)
            self._remember_dir(Path(chosen))

    def _browse_merge_files(self) -> None:
        chosen = self._ask_open_files("Choose PDF files to merge")
        if chosen:
            self._add_merge_paths(chosen)

    def _browse_merge_output(self) -> str:
        chosen = self._ask_save_file("Save merged PDF as", self.merge_output.get().strip())
        if chosen:
            self.merge_output.set(chosen)
            self._merge_auto_output = ""
            self._remember_dir(Path(chosen))
        return chosen

    def _on_drop_merge(self, event: Any) -> None:
        self._add_merge_paths(self._dropped_paths(event))

    def _add_merge_paths(self, raw_paths: Sequence[str]) -> None:
        candidates: List[Path] = []
        for raw in raw_paths:
            path = Path(raw)
            if path.is_dir():  # dropping a folder adds the PDFs inside it
                candidates.extend(
                    sorted(
                        (child for child in path.iterdir() if child.suffix.lower() == ".pdf"),
                        key=lambda child: child.name.lower(),
                    )
                )
            else:
                candidates.append(path)

        skipped: List[str] = []
        for path in candidates:
            if path.suffix.lower() != ".pdf":
                skipped.append(f"{path.name}: not a PDF file")
                continue
            try:
                pages = count_pages(path)
            except PydeefError as exc:
                skipped.append(str(exc))
                continue
            self._merge_counter += 1
            row_id = f"file{self._merge_counter}"
            self.merge_tree.insert(
                "", "end", iid=row_id, values=("", path.name, pages, str(path.parent))
            )
            self._merge_items[row_id] = (path, pages)
            self._remember_dir(path)

        self._refresh_merge_list()

        current_output = self.merge_output.get().strip()
        if not current_output or current_output == self._merge_auto_output:
            first = next(iter(self.merge_tree.get_children()), None)
            if first is not None:
                suggestion = str(self._merge_items[first][0].parent / "merged.pdf")
                self.merge_output.set(suggestion)
                self._merge_auto_output = suggestion

        if skipped:
            more = f"\n…and {len(skipped) - 8} more" if len(skipped) > 8 else ""
            messagebox.showwarning(
                "Some files were skipped", "\n".join(skipped[:8]) + more, parent=self.root
            )

    def _refresh_merge_list(self) -> None:
        rows = self.merge_tree.get_children()
        for number, row_id in enumerate(rows, start=1):
            self.merge_tree.set(row_id, "order", number)

        if rows:
            self.merge_hint.place_forget()
            total_pages = sum(self._merge_items[row_id][1] for row_id in rows)
            self.merge_summary.set(f"{plural(len(rows), 'file')} · {plural(total_pages, 'page')} in total")
        else:
            self.merge_hint.place(relx=0.5, rely=0.5, anchor="center")
            self.merge_summary.set("No files added yet")

    def _remove_selected(self) -> None:
        for row_id in self.merge_tree.selection():
            self.merge_tree.delete(row_id)
            self._merge_items.pop(row_id, None)
        self._refresh_merge_list()

    def _clear_merge_list(self) -> None:
        for row_id in self.merge_tree.get_children():
            self.merge_tree.delete(row_id)
        self._merge_items.clear()
        self._refresh_merge_list()

    def _move_up(self) -> None:
        selected = sorted(self.merge_tree.selection(), key=self.merge_tree.index)
        lowest = 0
        for row_id in selected:
            target = max(self.merge_tree.index(row_id) - 1, lowest)
            self.merge_tree.move(row_id, "", target)
            lowest = target + 1
        self._after_reorder(selected)

    def _move_down(self) -> None:
        selected = sorted(self.merge_tree.selection(), key=self.merge_tree.index, reverse=True)
        highest = len(self.merge_tree.get_children()) - 1
        for row_id in selected:
            target = min(self.merge_tree.index(row_id) + 1, highest)
            self.merge_tree.move(row_id, "", target)
            highest = target - 1
        self._after_reorder(selected)

    def _after_reorder(self, selected: Sequence[str]) -> None:
        self._refresh_merge_list()
        if selected:
            self.merge_tree.see(selected[0])

    def _on_merge(self) -> None:
        if self._busy:
            return
        rows = self.merge_tree.get_children()
        if len(rows) < 2:
            messagebox.showwarning("Not enough files", "Add at least two PDF files to merge.", parent=self.root)
            return
        sources = [self._merge_items[row_id][0] for row_id in rows]

        output_text = self.merge_output.get().strip() or self._browse_merge_output()
        if not output_text:
            return
        output = with_pdf_suffix(output_text)
        if not self._confirm_overwrite(output):
            return

        old_file: Optional[Path] = None
        if self.delete_old_enabled.get():
            old_text = self.delete_old_path.get().strip()
            if not old_text:
                messagebox.showwarning(
                    "Old file missing",
                    "Choose the old merged file to delete, or untick the option.",
                    parent=self.root,
                )
                return
            old_file = Path(old_text)
            if not messagebox.askyesno(
                "Delete old file?",
                f"After a successful merge, this file will be permanently deleted:\n\n{old_file}\n\nContinue?",
                icon="warning",
                parent=self.root,
            ):
                return

        self._run_task(
            lambda progress: merge_pdfs(sources, output, delete_old=old_file, progress=progress),
            self._merge_done,
            f"Merging {plural(len(sources), 'file')}…",
        )

    def _merge_done(self, result: MergeResult) -> None:
        self.status.set(f"Merged {plural(result.files, 'file')} into {result.output.name}")
        message = (
            f"Merged {plural(result.files, 'file')} ({plural(result.pages, 'page')}) into:\n{result.output}"
        )
        if result.deleted:
            message += f"\n\nDeleted the old file:\n{result.deleted}"
        if result.warnings:
            messagebox.showwarning("Merged, with notes", message + "\n\n" + "\n".join(result.warnings), parent=self.root)
        else:
            messagebox.showinfo("Merge complete", message, parent=self.root)
        if self.reveal_when_done.get():
            reveal_in_file_manager(result.output)

    # ------------------------------------------------------------------ #
    # Extract tab
    # ------------------------------------------------------------------ #
    def _build_extract_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=1)

        self.extract_input = tk.StringVar()
        input_entry, _ = self._path_field(
            tab, "Source PDF", self.extract_input, self._browse_extract_input, row=0
        )
        input_entry.bind("<FocusOut>", lambda _e: self._load_extract_input(self.extract_input.get().strip()))
        input_entry.bind("<Return>", lambda _e: self._load_extract_input(self.extract_input.get().strip()))
        self._register_drop(input_entry, self._on_drop_extract)

        self.extract_info = tk.StringVar(value="Choose a PDF, or drop one anywhere on this tab." if self.dnd else "Choose a PDF to begin.")
        ttk.Label(tab, textvariable=self.extract_info, style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 16)
        )

        ttk.Label(tab, text="Pages to extract", style="Section.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )
        self.extract_spec = tk.StringVar()
        spec_entry = ttk.Entry(tab, textvariable=self.extract_spec, width=34)
        spec_entry.grid(row=3, column=0, sticky="w")
        self.extract_spec.trace_add("write", lambda *_: self._update_extract_hint())

        self.extract_hint = tk.StringVar()
        self.extract_hint_label = ttk.Label(tab, textvariable=self.extract_hint, style="Muted.TLabel")
        self.extract_hint_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 18))

        self.extract_output = tk.StringVar()
        self._path_field(tab, "Save extracted pages as", self.extract_output, self._browse_extract_output, row=5)

        self.extract_button = ttk.Button(
            tab, text="Extract pages", style="Accent.TButton", command=self._on_extract
        )
        self.extract_button.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))

    def _browse_extract_input(self) -> None:
        chosen = self._ask_open_file("Choose the PDF to extract pages from")
        if chosen:
            self.extract_input.set(chosen)
            self._load_extract_input(chosen)

    def _browse_extract_output(self) -> str:
        chosen = self._ask_save_file("Save extracted pages as", self.extract_output.get().strip())
        if chosen:
            self.extract_output.set(chosen)
            self._extract_auto_output = ""
            self._remember_dir(Path(chosen))
        return chosen

    def _on_drop_extract(self, event: Any) -> None:
        paths = self._dropped_paths(event)
        if not paths:
            return
        self.extract_input.set(paths[0])
        self._load_extract_input(paths[0])
        if len(paths) > 1:
            self.status.set("Only the first dropped file is used on this tab.")

    def _load_extract_input(self, path_text: str) -> None:
        """Read the page count of the chosen PDF and suggest an output name."""
        if path_text == self._extract_loaded:
            return
        self._extract_loaded = path_text
        if not path_text:
            self._extract_total = None
            self.extract_info.set("Choose a PDF to begin.")
            self._update_extract_hint()
            return
        path = Path(path_text)
        try:
            total = count_pages(path)
        except PydeefError as exc:
            self._extract_total = None
            self.extract_info.set(str(exc))
            self._update_extract_hint()
            return

        self._extract_total = total
        self.extract_info.set(f"{path.name} · {plural(total, 'page')}")
        self._remember_dir(path)
        if not self.extract_output.get().strip() or self.extract_output.get() == self._extract_auto_output:
            suggestion = str(path.with_name(f"{path.stem}_extracted.pdf"))
            self.extract_output.set(suggestion)
            self._extract_auto_output = suggestion
        self._update_extract_hint()

    def _update_extract_hint(self) -> None:
        spec = self.extract_spec.get().strip()
        if not spec:
            self._set_extract_hint("Examples:  13   ·   1-3, 5   ·   8-  (page 8 to the end)", "Muted.TLabel")
        elif self._extract_total is None:
            self._set_extract_hint("Choose a valid PDF to check the page numbers.", "Muted.TLabel")
        else:
            try:
                pages = parse_page_spec(spec, self._extract_total)
            except PydeefError as exc:
                self._set_extract_hint(str(exc), "Error.TLabel")
            else:
                self._set_extract_hint(
                    f"{plural(len(pages), 'page')} selected: {summarize_pages(pages)}", "Ok.TLabel"
                )

    def _set_extract_hint(self, text: str, style_name: str) -> None:
        self.extract_hint.set(text)
        self.extract_hint_label.configure(style=style_name)

    def _on_extract(self) -> None:
        if self._busy:
            return
        source_text = self.extract_input.get().strip()
        if not source_text:
            messagebox.showwarning("Choose a PDF", "Choose the PDF to extract pages from.", parent=self.root)
            return
        spec = self.extract_spec.get().strip()
        if not spec:
            messagebox.showwarning(
                "Choose pages", "Enter the page(s) to extract, for example 13 or 1-3, 5.", parent=self.root
            )
            return

        output_text = self.extract_output.get().strip() or self._browse_extract_output()
        if not output_text:
            return
        source, output = Path(source_text), with_pdf_suffix(output_text)
        if not self._confirm_overwrite(output):
            return

        self._run_task(
            lambda _progress: extract_pages(source, output, spec),
            self._extract_done,
            "Extracting pages…",
            determinate=False,
        )

    def _extract_done(self, result: ExtractResult) -> None:
        self.status.set(f"Saved {plural(len(result.pages), 'page')} to {result.output.name}")
        messagebox.showinfo(
            "Extraction complete",
            f"Saved {plural(len(result.pages), 'page')} (from {result.source_pages}) to:\n{result.output}\n\n"
            f"Pages: {summarize_pages(result.pages)}",
            parent=self.root,
        )
        if self.reveal_when_done.get():
            reveal_in_file_manager(result.output)


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #
def diagnose() -> int:
    """Print what is needed to debug missing logos/icons (``pydeef --diagnose``)."""
    out = sys.stdout.write if sys.stdout else (lambda text: None)
    out(f"pydeef {__version__}\n")
    out(f"Python {sys.version.split()[0]} on {sys.platform}\n")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        out(f"Cannot open a window: {exc}\n")
        return 1
    root.withdraw()
    out(f"Tk {root.tk.call('info', 'patchlevel')}\n")
    out(f"Assets folder: {asset_path('')}\n")
    problems = 0
    for name in BUNDLED_IMAGES:
        path = asset_path(name)
        if not path.is_file():
            out(f"  MISSING  {name}\n")
            problems += 1
            continue
        try:
            image = load_photo(root, name)
            out(f"  ok       {name}  ({image.width()}x{image.height()} px, {path.stat().st_size} bytes)\n")
        except (tk.TclError, OSError) as exc:
            out(f"  FAILED   {name}: {exc}\n")
            problems += 1
    root.destroy()
    out("All images load fine.\n" if not problems else f"{problems} problem(s) found.\n")
    return 1 if problems else 0


def run() -> None:
    """Start the pydeef window and block until it is closed."""
    _prepare_platform()
    try:
        root, dnd_enabled = create_root()
    except tk.TclError as exc:
        if sys.stderr:
            sys.stderr.write(f"pydeef could not open a window: {exc}\n")
        raise SystemExit(1)
    PydeefApp(root, dnd_enabled)
    root.mainloop()


if __name__ == "__main__":
    run()
