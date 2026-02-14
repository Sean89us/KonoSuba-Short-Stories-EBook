# XHTML Structure Guide (Story Files)

**Goal:** Keep every story XHTML file structurally consistent so reading systems behave predictably, diffs stay clean, and we can validate/automate formatting.

**Canonical reference:** `thedivinehandoftheotherworld.xhtml`

This guide is **structure-focused** (tags/ordering/required blocks). For prose, punctuation, and localization rules, keep using `LOCALIZATION_STYLE_GUIDE.md`.

---

## 1) Required document skeleton

Every story file should be valid XHTML (well-formed XML) with this top-level structure:

1. XML prolog on the first line:
   - `<?xml version='1.0' encoding='utf-8'?>`
2. Root `<html>` element:
   - Must include XHTML namespace.
   - Must include `xmlns:epub`.
   - Must include `epub:prefix`.
   - Must include `lang="en"` and `xml:lang="en"`.
3. `<head>` with a single `<title>`.
4. `<body>` with:
   - A single `<h1>` title
   - A metadata block (see §2)
   - A horizontal rule `<hr/>`
   - Story content as a sequence of block elements (usually `<p>`)
   - A final `<hr/>` before closing `</body>`

### Canonical skeleton (example)

```xml
<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#"
      lang="en" xml:lang="en">

<head>
  <title>…</title>
</head>

<body>

  <h1>…</h1>

  <p>Translator: …</p>
  <p>Editors: …</p>
  <p>Occurrence: …</p>

  <hr/>

  <!-- story paragraphs, headings, images, etc. -->

  <hr/>

</body>

</html>
```

Notes:
- Indentation should match the canonical style (2 spaces per indent level).
- Keep blank lines between logical blocks (as shown above).

---

## 2) Metadata block rules

Immediately under the `<h1>`, use `<p>` lines for metadata.

- **Required:** `Translator:` should exist in every story file.
- **Optional:** `Editors:` and `Occurrence:` are not always present; include them when known.
- **Keep these labels exactly** (case and punctuation) when present:
  - `Translator:`
  - `Editors:`
  - `Occurrence:`
- If an optional field is unknown/unavailable, omit that entire `<p>` line rather than inventing new labels.
- Do not rename labels (e.g., avoid `Translation:`, `Editing:`, `Timeline:`).

---

## 3) Content block rules (core)

Within the story body (after the first `<hr/>`):

- Use `<p>` for normal paragraphs and dialogue lines.
- Use `<p><strong>Part N</strong></p>` when the story is explicitly split into parts (common in Blu-ray shorts).
- Images (when present) should be block-level and XHTML-safe. Canonical pattern:

```xml
  <p>
    <img src="FILENAME.jpeg" title=""/>
  </p>
```

(If the file already uses a different working pattern consistently, keep it consistent across the collection.)

---

## 4) Allowed optional blocks

These are allowed as long as the required skeleton remains intact:

- Translator notes in `<p>` (often bracketed like `[Note: …]`) placed in the metadata area **before** the first `<hr/>`.
- Additional metadata `<p>` lines (rare). If added, keep them grouped with the other metadata under `<h1>`.
- Part headings (`Part 1`, `Part 2`, etc.)
- Ending illustration block (see §3).

---

## 5) Validation checklist

Before considering a story “done”:

- XML well-formedness parses successfully.
- Exactly one `<h1>`.
- `<title>` exists and matches the story title.
- Metadata labels (if present) are exactly `Translator:`, `Editors:`, `Occurrence:`.
- `<hr/>` exists after metadata and again near the end.

### Quick local command (macOS)

From the EPUB folder:

```sh
python3 - <<'PY'
import xml.etree.ElementTree as ET
ET.parse('YOUR_FILE.xhtml')
print('XML parse: OK')
PY
```

## File Naming

Story XHTML filenames should follow this convention:

- **Lowercase only**
- **No spaces**
- **No dashes/hyphens (`-`)**
- **No underscores (`_`)**
- Use the existing “run-together” word style already present in this EPUB (e.g., `onacertainmidsummersnight.xhtml`).

If a rename is ever necessary, remember that EPUBs don’t discover files automatically:

- Update references in the package/manifest (typically `content.opf`).
- Update any navigation/toc references (e.g., `nav.xhtml`, `toc.ncx`) if they point at the renamed file.
