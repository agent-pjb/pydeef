<p align="center">
  <img src="assets/logo.png" alt="pydeef logo" width="220">
</p>

<h1 align="center">pydeef</h1>

<p align="center">
  <b>Merge PDFs and extract pages — fast, simple and 100% offline.</b><br>
  A small desktop app built with Python, Tkinter and <a href="https://github.com/py-pdf/pypdf">pypdf</a>.
</p>

<p align="center">
  <a href="https://github.com/agent-pjb/pydeef/actions/workflows/ci.yml"><img src="https://github.com/agent-pjb/pydeef/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-2f6bff" alt="Platforms">
  <img src="https://img.shields.io/badge/GUI-Tkinter-ff3b30" alt="Tkinter GUI">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license"></a>
</p>

<!--
  Add a screenshot after your first run, then uncomment:

  <p align="center">
    <img src="docs/screenshot.png" alt="pydeef screenshot" width="760">
  </p>
-->

---

## Table of contents

- [Why pydeef?](#why-pydeef)
- [Features](#features)
- [Quick start](#quick-start)
- [How to use it](#how-to-use-it)
  - [Merge PDFs](#merge-pdfs)
  - [Extract pages](#extract-pages)
  - [Page selection syntax](#page-selection-syntax)
  - [Keyboard shortcuts](#keyboard-shortcuts)
- [Safety and privacy](#safety-and-privacy)
- [Use it as a Python library](#use-it-as-a-python-library)
- [Coming from the original scripts](#coming-from-the-original-scripts)
- [Project structure](#project-structure)
- [Development](#development)
- [Build a standalone app](#build-a-standalone-app)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Why pydeef?

Merging a few PDFs or pulling a single page out of a big document should not
need an online service, an account, or a 500 MB suite. **pydeef** does exactly
two things, and does them well:

1. **Merge** several PDFs into one, in the order you choose.
2. **Extract** one page, a list of pages or a range from a PDF into a new file.

Everything happens on your computer. Your documents are never uploaded anywhere.

## Features

**Merge**
- Add files with a dialog, or **drag & drop** files (or a whole folder) onto the window
- Reorder with **Move up / Move down**; see the page count of every file and the total
- Optional: **delete an old merged file** after the new one is saved successfully
- Output name is suggested for you; `.pdf` is added automatically

**Extract**
- Pull out a single page (`13`), a list (`1, 4, 9`), ranges (`2-6`) or "to the end" (`8-`)
- **Live validation**: the app checks your selection against the real page count as you type

**Quality of life**
- Dark theme that matches the logo, HiDPI-aware on Windows
- Work runs on a background thread with a progress bar — the window never freezes
- Clear, friendly messages for missing, corrupt or password-protected PDFs
- Optional "show file in folder when done"
- Cross-platform: Windows, macOS and Linux

## Quick start

### Requirements

- **Python 3.9 or newer**
- **Tkinter** (bundled with Python on Windows and macOS; on Linux you may need to install it — see [Troubleshooting](#troubleshooting))

### Option A — run from source

```bash
git clone https://github.com/agent-pjb/pydeef.git
cd pydeef

# (recommended) create a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

### Option B — install with pip

```bash
pip install git+https://github.com/agent-pjb/pydeef.git
pydeef                 # or: python -m pydeef
```

> `pydeef --version` prints the installed version without opening the window, and
> `pydeef --diagnose` checks your Tk installation and the bundled images (handy for bug reports).

## How to use it

### Merge PDFs

1. Open the **Merge PDFs** tab.
2. Click **Add files…** — or drag PDFs (or a folder of PDFs) into the list.
3. Put them in the right order with **↑ Move up** / **↓ Move down**. Files are merged from top to bottom.
4. Choose where to save the result under **Save merged PDF as**.
5. *(Optional)* Tick **After a successful merge, delete an old merged file** and pick that file. It is deleted only after the new file has been written, and only after you confirm.
6. Click **Merge PDFs**.

### Extract pages

1. Open the **Extract pages** tab.
2. Choose the **Source PDF** (or drop one onto the tab). pydeef shows how many pages it has.
3. Type the pages you want under **Pages to extract**, e.g. `13` or `1-3, 5`.
   A green line confirms what will be extracted; a red line explains any mistake.
4. Choose where to save the result (a name is suggested).
5. Click **Extract pages**. The original PDF is never modified.

### Page selection syntax

| You type      | You get                                    |
|---------------|--------------------------------------------|
| `13`          | page 13                                    |
| `1-3`         | pages 1, 2 and 3                           |
| `1-3, 5`      | pages 1, 2, 3 and 5                        |
| `8-`          | page 8 to the last page                    |
| `5, 1-2, 14-` | pages 5, 1, 2, then 14 to the end (in that order) |

Commas or semicolons separate items. Pages are written in the order you list
them, and repeated pages are included only once. Page numbers start at 1.

### Keyboard shortcuts

| Shortcut                | Action                         |
|-------------------------|--------------------------------|
| `Ctrl/Cmd + O`          | Add PDFs to merge              |
| `Ctrl/Cmd + E`          | Choose the PDF to extract from |
| `Delete` / `Backspace`  | Remove the selected files from the merge list |
| `Ctrl/Cmd + Q`          | Quit                           |

## Safety and privacy

- **Offline by design.** pydeef makes no network connections.
- **Your sources are never modified.** Merging and extracting always create a *new* file.
- **Atomic saving.** Output is written to a temporary file and moved into place only when complete,
  so a failure can never leave a half-written or corrupted PDF — and an existing file you chose to
  replace stays intact if something goes wrong.
- **Overwrite protection.** You are asked before an existing file is replaced, and the *Extract* tab
  refuses to overwrite its own source PDF.
- **Deletion is opt-in and double-checked.** The "delete old file" option is off by default, asks for
  confirmation, and runs only after a successful merge.
- **Passwords.** PDFs protected with an *empty* user password (very common) open transparently.
  PDFs that need a real password are rejected with a clear message — pydeef does not try to bypass protection.

## Use it as a Python library

The PDF logic lives in [`pydeef/core.py`](src/pydeef/core.py) and has no GUI dependencies, so you can
script it directly:

```python
from pydeef.core import merge_pdfs, extract_pages, extract_specific_page, PydeefError

try:
    # Merge, top to bottom
    result = merge_pdfs(["test-pdf1.pdf", "test-pdf2.pdf"], "pds-updated.pdf")
    print(result.files, "files,", result.pages, "pages ->", result.output)

    # Merge and remove the previous merged file once the new one is safely written
    merge_pdfs(
        ["test-pdf1.pdf", "test-pdf2.pdf"],
        "pds-updated.pdf",
        delete_old="merged_pdfs.pdf",
    )

    # Extract page 13 (same as the original extract_specific_page script)
    extract_specific_page("input_file.pdf", "output_file.pdf", 13)

    # Extract several pages and ranges
    extract_pages("input_file.pdf", "picked.pdf", "1-3, 5, 8-")

except PydeefError as error:
    print("Problem:", error)   # always a human-readable message
```

| Function | What it does |
|----------|--------------|
| `merge_pdfs(inputs, output, *, delete_old=None, progress=None)` | Merge two or more PDFs; returns a `MergeResult` |
| `extract_pages(input_path, output, pages)` | `pages` is a string like `"1-3, 5"` or a list of 1-based numbers; returns an `ExtractResult` |
| `extract_specific_page(input_pdf_path, output_pdf_path, page_number)` | One page — mirrors the original script |
| `parse_page_spec(spec, total_pages)` | Turn `"1-3, 5, 8-"` into `[1, 2, 3, 5, 8, …]` |
| `count_pages(path)` / `open_pdf(path)` | Page count / a ready-to-use `pypdf.PdfReader` |

## Coming from the original scripts

pydeef started as two small scripts. Here is where everything went:

| Original script | In pydeef |
|-----------------|-----------|
| Merge with `PyPDF2.PdfMerger` | **Merge PDFs** tab → `core.merge_pdfs()` |
| "If the old merged file exists, delete it" | The optional **delete an old merged file** checkbox (`delete_old=`). It now runs *after* a successful merge instead of being a precondition for merging |
| `extract_specific_page(input, output, 13)` | **Extract pages** tab → `core.extract_pages()` (also still available as `core.extract_specific_page()`) |
| `PyPDF2` + `pypdf` | Just **`pypdf`**. Its `PdfWriter.append()` replaces `PdfMerger`, which is deprecated and removed in modern pypdf |

## Project structure

```text
pydeef/
├── assets/
│   ├── logo.png               # logo used in this README
│   ├── icon.ico               # Windows app icon (multi-size)
│   └── icon.icns              # macOS app icon
├── src/
│   └── pydeef/
│       ├── __init__.py        # version
│       ├── __main__.py        # `python -m pydeef` / `pydeef` command
│       ├── core.py            # PDF logic (no GUI imports)
│       ├── gui.py             # Tkinter user interface
│       └── assets/            # logo + icons loaded by the running app (PNG, GIF fallback, ICO)
├── tests/
│   ├── helpers.py             # builds tiny PDFs on the fly
│   ├── test_core.py           # tests for merge / extract / page parsing
│   └── test_gui_logic.py      # headless tests of the GUI logic
├── .github/                   # CI workflow, issue and PR templates
├── main.py                    # run from a source checkout (also the PyInstaller entry point)
├── pyproject.toml             # packaging metadata
├── requirements.txt           # runtime dependencies
├── requirements-dev.txt       # + pytest and PyInstaller
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

The GUI is intentionally thin: it validates input, calls `core` on a background thread, and shows results.
All PDF behaviour lives in `core.py`, which is why it is easy to test and reuse.

## Development

```bash
pip install -r requirements-dev.txt
pip install -e . --no-deps

pytest                                   # run all tests
python -m unittest discover -s tests -v  # ...or with the standard library only
python main.py                           # start the app
```

- The tests generate their own tiny PDFs, so there are no fixtures to maintain.
- The GUI logic is tested **headlessly** against lightweight Tk stand-ins, so the whole suite runs
  without a display (including on CI). Visual appearance still needs a manual look.
- GitHub Actions runs the tests on Windows, macOS and Linux for several Python versions.

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions.

## Build a standalone app

Turn pydeef into a double-clickable program (no Python needed on the target machine) with
[PyInstaller](https://pyinstaller.org). Run the command for your OS from the project root;
the result appears in `dist/`.

**Windows**

```bat
pip install -r requirements-dev.txt
pyinstaller --noconfirm --windowed --onefile --name pydeef --icon assets/icon.ico --paths src --add-data "src/pydeef/assets;pydeef/assets" --collect-all tkinterdnd2 main.py
```

**macOS** (produces `dist/pydeef.app`)

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --windowed --name pydeef --icon assets/icon.icns --paths src --add-data "src/pydeef/assets:pydeef/assets" --collect-all tkinterdnd2 main.py
```

**Linux**

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --windowed --onefile --name pydeef --paths src --add-data "src/pydeef/assets:pydeef/assets" --collect-all tkinterdnd2 main.py
```

> The only difference between the commands is the icon format and the `--add-data` separator
> (`;` on Windows, `:` on macOS/Linux). PyInstaller builds are per-platform: build on the OS you
> are targeting. If a build misses a file, check PyInstaller's output for warnings.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'tkinter'` (Linux) | `sudo apt install python3-tk` (Debian/Ubuntu) · `sudo dnf install python3-tkinter` (Fedora) · `sudo pacman -S tk` (Arch) |
| Tkinter missing on macOS | Use the installer from [python.org](https://www.python.org/downloads/), or `brew install python-tk` |
| Tkinter missing on Windows | Re-run the Python installer → *Modify* → tick **tcl/tk and IDLE** |
| Logo or window icon is missing | Run `python main.py --diagnose` (or `pydeef --diagnose`). It prints your Tk version and checks every bundled image, so you can see exactly which one fails and why. Run the app from a terminal too: image problems are logged there instead of being hidden. Make sure you copied the whole `src/pydeef/assets/` folder |
| Drag & drop does nothing | `pip install tkinterdnd2`. The *About* dialog (Help → About) tells you whether drag & drop is active. Everything else works without it |
| "…is password-protected" | pydeef can't open PDFs that need a password. Remove the protection in the program that created the file, then try again |
| "…could not be read as a PDF" | The file is damaged or not a real PDF. Try re-exporting it, or opening and re-saving it in a PDF viewer |
| "…uses encryption that needs an extra package" | `pip install cryptography` (it is part of `requirements.txt`) |
| Text looks tiny or blurry on a HiDPI Windows display | pydeef enables DPI awareness automatically; make sure you run the app from the same Python that you installed the requirements into |
| Window doesn't open over SSH / in a container | pydeef needs a graphical display (`DISPLAY` on Linux) |

## Roadmap

Ideas for future versions — contributions welcome:

- [ ] Split a PDF into one file per page, or into chunks of *N* pages
- [ ] Page thumbnails / preview
- [ ] Reorder, rotate and delete individual pages
- [ ] Open password-protected PDFs when the user knows the password
- [ ] Light theme and a theme switcher
- [ ] A command-line interface (`pydeef merge a.pdf b.pdf -o out.pdf`)
- [ ] Automated release builds for Windows, macOS and Linux

## Contributing

Bug reports, ideas and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first
and use the issue templates. If you hit a problem with a specific file, a small sample without private
data is extremely helpful.

## License

Released under the [MIT License](LICENSE).

## Acknowledgements

- [pypdf](https://github.com/py-pdf/pypdf) — the PDF engine doing the real work
- [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) — optional drag & drop for Tkinter
- Python's built-in [Tkinter](https://docs.python.org/3/library/tkinter.html) for the interface
