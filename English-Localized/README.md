# English-Localized (EPUB source)

This folder contains the **English-localized** track of the KonoSuba short story collection.

It is intended to be the “reads like native modern English” version of the book while still remaining:

- **EPUB-valid** (well-formed XHTML/XML)
- **Structurally consistent** across all story files
- **Conservative in scope** (localization + mechanical typography, not new scenes or reordering)

If you want the “minimal wording changes / mostly-mechanical cleanup” track, see the repository’s `Unchanged-Translations/` folder instead.

## What “English-Localized” means here

This track applies a localization pass that typically includes:

- Removing honorifics / JP address markers (e.g., `-san`, `-sama`, `senpai`, `onee-chan`)
- Rewriting overly literal phrasing into more natural English
- Normalizing canon terms for consistency across the collection
- Upgrading punctuation/typography for EPUB readability:
  - curly quotes `“ ”` / `‘ ’`
  - ellipsis `…`
  - em dash `—`

Preferences and constraints:

- Prefer **US English** spelling/grammar/punctuation when there’s a choice.
- Do **not** break XHTML validity or the required file structure.
- Do **not** invent new jokes, lore, or exposition.
- Do **not** rename files casually (filenames are referenced by `content.opf` / navigation documents).

The detailed rules live in:

- [LOCALIZATION_STYLE_GUIDE.md](LOCALIZATION_STYLE_GUIDE.md)
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

Read-only scan for XHTML structure compliance and ASCII punctuation that should be localized.

```sh
python3 tools/scan_story_xhtml.py --epub-dir English-Localized/EPUB
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
python3 tools/fix_story_xhtml.py --epub-dir English-Localized/EPUB --check
```

Apply fixes in-place:

```sh
python3 tools/fix_story_xhtml.py --epub-dir English-Localized/EPUB
```

Optionally insert a localization credit line into the metadata block:

```sh
python3 tools/fix_story_xhtml.py --epub-dir English-Localized/EPUB --add-localization-credit
```

### 3) Proofreading report (and optional conservative fixes)

Generates a markdown report of common proofreading issues.

Report only:

```sh
python3 tools/epub_proofread.py --epub-dir English-Localized/EPUB --out English-Localized/proofread_report.md
```

Apply conservative mechanical fixes first, then report:

```sh
python3 tools/epub_proofread.py --fix --epub-dir English-Localized/EPUB --out English-Localized/proofread_report.md
```

Optional LanguageTool integration (requires extra Python deps and Java). This can be helpful, but keep it conservative:

```sh
python3 tools/epub_proofread.py --fix --lt-fix --epub-dir English-Localized/EPUB --out English-Localized/proofread_report.md
```

### 4) Regenerate `content.opf`, `nav.xhtml`, and `toc.ncx`

This rebuilds navigation/manifest files based on the files on disk and the existing spine order.

Design notes:

- Preserves existing OPF `<metadata>` (only updates `dcterms:modified`)
- Preserves spine order (does not reorder your book)
- Uses each story’s `<h1>` (fallback: `<title>`, fallback: filename) for TOC labels

```sh
python3 tools/regenerate_epub_toc.py --epub-dir English-Localized/EPUB
```

### 5) Package the EPUB

Creates a `.epub` zip with correct `mimetype` handling.

```sh
python3 tools/package_epub.py --src English-Localized --out dist/English-Localized.epub
```

### 6) Validate (recommended)

Use `epubcheck` to catch structural issues.

```sh
brew install epubcheck

epubcheck dist/English-Localized.epub
```
## Adding a story

1. Provide the story text to your **AI code assistant of choice** and ask it to generate a new `.xhtml` story file that follows the relevant guides:

```text
Example AI Prompt:

Follow the Localization Style Guide and XHTML Structure guide located in `English-Localized` to create and a new story in the `English-Localized/EPUB` folder. The story is currently a raw translation, so follow the localization guide to update the grammar, spelling, phrasing, punctuation, and so forth. Once the story file exists, ensure that it is added to the index and metadata files (content.opf`, `nav.xhtml`, and `toc.ncx`) after the story "Aqua Sensei". This story is titled "Some KonoSuba Story" and here is the full text:

<insert full story text>
```

2. Run the scan/fix tools as needed.
3. Package and validate.

## Editing a story

1. Edit the `*.xhtml` file in `EPUB/`.
2. Follow the guides:
   - [LOCALIZATION_STYLE_GUIDE.md](LOCALIZATION_STYLE_GUIDE.md)
   - [XHTML_STRUCTURE_GUIDE.md](XHTML_STRUCTURE_GUIDE.md)
3. Run the scan/fix tools as needed.
4. Regenerate navigation:
   - `python3 tools/regenerate_epub_toc.py --epub-dir English-Localized/EPUB`
5. Package and validate.

## Tooling dependencies

At minimum: Python 3.

Some scripts use `lxml`.

LanguageTool support in `tools/epub_proofread.py` is optional and requires additional setup (e.g., `language-tool-python` and Java).
