# Contributing to pydeef

Thanks for your interest in improving pydeef! Bug reports, ideas and pull
requests are all welcome.

## Getting set up

```bash
git clone https://github.com/agent-pjb/pydeef.git
cd pydeef

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e . --no-deps

python main.py          # start the app
pytest                  # run the tests
```

> Linux users may need Tkinter: `sudo apt install python3-tk`.

## How the code is organised

| File | Responsibility |
|------|----------------|
| `src/pydeef/core.py` | All PDF logic. **No GUI imports.** Raises `PydeefError` with user-friendly messages. |
| `src/pydeef/gui.py`  | The Tkinter window. Stays thin: it validates input, runs `core` functions on a background thread and shows results. |
| `tests/test_core.py` | Tests for the PDF logic (PDFs are generated on the fly). |
| `tests/test_gui_logic.py` | Headless tests for the GUI logic using Tk stand-ins. |

Rules of thumb:

1. New PDF feature? Put the logic in `core.py` first, with tests, then wire it up in `gui.py`.
2. Never write directly to the user's output path - use the atomic helper in `core.py`.
3. Never block the Tk main loop; use `PydeefApp._run_task` for anything slow.
4. Keep error messages friendly and actionable.
5. Don't commit PDFs (they are ignored on purpose). Generate fixtures in tests instead.

## Pull requests

- Keep PRs focused; one feature or fix per PR is ideal.
- Add or update tests, and run `pytest` before pushing.
- Add a line to `CHANGELOG.md` under an "Unreleased" heading.
- Describe *why* the change is useful, not only what it does.

## Reporting bugs

Please use the bug-report template and include your OS, Python version and the
exact error message. If a particular PDF triggers the problem, a small sample
without private data is extremely helpful.
