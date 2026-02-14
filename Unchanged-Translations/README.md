# Unchanged-Translations (EPUB source)

This folder contains the **unchanged / baseline translation** track of the KonoSuba short story collection.

It is intended to be the “keep the original translation wording intact” version of the book while still remaining:

- **EPUB-valid** (well-formed XHTML/XML)
- **Structurally consistent** across all story files
- **Conservative in scope** (mechanical cleanup, not localization)

If you want the “English localization pass / reads like native modern English” track, see `English-Localized/`.

## What “Unchanged-Translations” means here

This track focuses on **mechanical and editorial cleanup** while preserving the original translation as much as possible.

Typical edits include:

- Fixing obvious typos
- Light grammar/punctuation cleanup
- Consistent emphasis / formatting where it improves readability
- Consistent XHTML structure so the EPUB can be validated and packaged reliably

Preferences and constraints:

- Prefer **UK English** spelling/grammar/punctuation when there’s a choice.
- Do **not** rewrite prose for “localization” or remove JP-isms/honorifics as a style goal.
- Keep intentional translation flourishes (e.g., Vanir’s `Moi/moi`) as described in the style guide.
- Do **not** break XHTML validity or the required file structure.
- Do **not** rename files casually (filenames are referenced by `content.opf` / navigation documents).

The detailed rules live in:

- [STYLE_GUIDE.md](STYLE_GUIDE.md)
- [XHTML_STRUCTURE_GUIDE.md](XHTML_STRUCTURE_GUIDE.md)

## Folder layout

This directory is an EPUB build root, with the standard structure:

- `mimetype` — required by the EPUB spec (must be first and uncompressed in the final ZIP)
- `META-INF/` — container metadata
- `EPUB/` — the actual book payload
  - `*.xhtml` story files (plus `cover.xhtml`, `copyright.xhtml`, etc.)
  - `content.opf` — package metadata/manifest/spine
  - `nav.xhtml` and `toc.ncx` — navigation documents

## Common workflows

All tooling lives in `../tools/` and is designed to be run from the repo root.

### 1) Scan story structure + punctuation

Read-only scan for XHTML structure compliance and (optionally) ASCII punctuation patterns.

```sh
python3 tools/scan_story_xhtml.py --epub-dir Unchanged-Translations/EPUB
```

### 2) Apply safe mechanical fixes (optional)

This script is intentionally narrow and tries to avoid touching tag attributes.

It can:

- Convert straight ASCII quotes/apostrophes in **text nodes** to curly quotes
- Convert `...` → `…` and `--`/`---` → `—` in **text nodes**
- Normalize metadata labels under `<h1>` (Translator/Editors/Occurrence)
- Ensure a final `<hr/>` exists before `</body>`
- Ensure `<title>` matches `<h1>`

Dry-run (shows which files would change):

```sh
python3 tools/fix_story_xhtml.py --epub-dir Unchanged-Translations/EPUB --check
```

Apply fixes in-place:

```sh
python3 tools/fix_story_xhtml.py --epub-dir Unchanged-Translations/EPUB
```

### 3) Proofreading report (and optional conservative fixes)

Generates a markdown report of common proofreading issues.

Report only:

```sh
python3 tools/epub_proofread.py --epub-dir Unchanged-Translations/EPUB --out Unchanged-Translations/proofread_report.md
```

Apply conservative mechanical fixes first, then report:

```sh
python3 tools/epub_proofread.py --fix --epub-dir Unchanged-Translations/EPUB --out Unchanged-Translations/proofread_report.md
```

Optional LanguageTool integration (requires extra Python deps and Java):

```sh
python3 tools/epub_proofread.py --fix --lt-fix --epub-dir Unchanged-Translations/EPUB --out Unchanged-Translations/proofread_report.md
```

### 4) Regenerate `content.opf`, `nav.xhtml`, and `toc.ncx`

This rebuilds navigation/manifest files based on the files on disk and the existing spine order.

Design notes:

- Preserves existing OPF `<metadata>` (only updates `dcterms:modified`)
- Preserves spine order (does not reorder your book)
- Uses each story’s `<h1>` (fallback: `<title>`, fallback: filename) for TOC labels

```sh
python3 tools/regenerate_epub_toc.py --epub-dir Unchanged-Translations/EPUB
```

### 5) Package the EPUB

Creates a `.epub` zip with correct `mimetype` handling.

```sh
python3 tools/package_epub.py --src Unchanged-Translations --out dist/Unchanged-Translations.epub
```

### 6) Validate (recommended)

Use `epubcheck` to catch structural issues.

```sh
brew install epubcheck

epubcheck dist/Unchanged-Translations.epub
```

## Adding a story

1. Provide the story text to your AI code assistant of choice and ask it to generate a new `.xhtml` story file that follows the relevant guides:

```text
Example AI Prompt:

Follow the Style Guide and XHTML Structure guide located in `Unchanged-Translations` to create a new story in the `Unchanged-Translations/EPUB` folder. Once the story file exists, ensure that it is added to the index and metadata files (`content.opf`, `nav.xhtml`, and `toc.ncx`) after the story "Aqua Sensei". This story is titled "Some KonoSuba Story" and here is the full text:

<insert full story text>
```
2. Run the scan/fix tools as needed.
3. Package and validate.


## Editing a story

1. Edit the `*.xhtml` file in `EPUB/`.
2. Follow the guides:
   - [STYLE_GUIDE.md](STYLE_GUIDE.md)
   - [XHTML_STRUCTURE_GUIDE.md](XHTML_STRUCTURE_GUIDE.md)
3. Run the scan/fix tools as needed.
4. Regenerate navigation:
   - `python3 tools/regenerate_epub_toc.py --epub-dir Unchanged-Translations/EPUB`
5. Package and validate.

## Tooling dependencies

At minimum: Python 3.

Some scripts use `lxml`.

LanguageTool support in `tools/epub_proofread.py` is optional and requires additional setup (e.g., `language-tool-python` and Java).
