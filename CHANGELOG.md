# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-09

### Added
- Desktop GUI (Tkinter) with a dark theme that matches the pydeef logo.
- **Merge PDFs**: add files via dialog, drag & drop (files or whole folders),
  reorder with *Move up / Move down*, page counts per file, live totals.
- Optional "delete an old merged file after a successful merge" (from the
  original merge script), protected by a confirmation dialog.
- **Extract pages**: single pages, lists and ranges such as `13`, `1-3, 5`, `8-`,
  with live validation against the real page count.
- Background worker thread and progress bar - the window never freezes.
- Atomic saving: an existing output file is never left half-written.
- Friendly errors for missing, corrupt and password-protected PDFs.
- Optional "show file in folder when done".
- `pydeef.core` module that can be used without the GUI.
- Robust logo/icon loading: images are loaded as data (avoids file-path encoding problems),
  the window icon is supplied in several sizes, the bundled `.ico` uses classic BMP frames,
  a GIF fallback covers very old Tk builds, and image problems are logged instead of ignored.
- `pydeef --diagnose` prints the Tk version and checks every bundled image.
- Test-suite (core + headless GUI logic) and GitHub Actions CI.

### Changed (compared with the original scripts)
- Merging uses `pypdf.PdfWriter.append` instead of the deprecated
  `PyPDF2.PdfMerger`, so one library (`pypdf`) powers everything.

[1.0.0]: https://github.com/YOUR-USERNAME/pydeef/releases/tag/v1.0.0
