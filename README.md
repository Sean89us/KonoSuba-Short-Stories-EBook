# KonoSuba — Short Stories Collection (EPUB)

This repository contains source files and build tooling used to collect **KonoSuba** short stories into a single, consistent, easy-to-read EPUB.

It is organized into two parallel tracks:

- `Unchanged-Translations/`: Story files kept as close as possible to their baseline wording, with only mechanical/formatting cleanup to ensure consistent XHTML/EPUB structure.
- `English-Localized/`: The same content, but with an English localization pass focused on readability and consistency (e.g., typography like curly quotes/ellipses/em-dashes) while keeping the work EPUB-valid.

Both tracks contain:

- `EPUB/`: The EPUB payload (XHTML content documents, navigation documents, OPF/NCX, images, etc.)
- `META-INF/`: EPUB container metadata

The `tools/` folder contains Python scripts that help scan, normalize, regenerate navigation/packaging files, and package the final EPUB.

## Releases

Releases should be cut when tags are pushed. This should generate the epub files and attach them to the release.

## Weekend Project Background

This was a weekend project for me with two goals:

1. **Collect all known KonoSuba short stories in one place** and publish them as a single ebook that’s easy to read on E-Readers / tablets.
2. **Expand my knowledge of using AI tooling for practical purposes**, especially around automation and “mechanical” editing tasks (XHTML consistency, typography normalization, metadata consistency, and EPUB navigation generation).

## Repository Layout

- `Unchanged-Translations/`
  - `STYLE_GUIDE.md` and `XHTML_STRUCTURE_GUIDE.md`: Rules for consistent markup and structure.
  - `EPUB/`: XHTML story files plus `content.opf`, `nav.xhtml`, `toc.ncx`, etc.
- `English-Localized/`
  - `LOCALIZATION_STYLE_GUIDE.md` and `XHTML_STRUCTURE_GUIDE.md`: Localization typography rules and required XHTML structure.
  - `EPUB/`: Localized XHTML story files plus `content.opf`, `nav.xhtml`, `toc.ncx`, etc.
- `tools/`
  - Scripts to scan/fix story XHTML, regenerate OPF/TOC/nav documents, and package an EPUB.

## Building / Packaging

The exact packaging workflow is handled by the scripts in `tools/`. Typical usage is:

1. Ensure the story XHTML files are valid and consistent.
2. Ensure `content.opf`, `nav.xhtml`, and `toc.ncx` match the current story titles/headings.
3. Package the directory structure into an `.epub`.
  - `python3 tools/package_epub.py --src Unchanged-Translations --out dist/Unchanged-Translations.epub`
  - `python3 tools/package_epub.py --src English-Localized --out dist/English-Localized.epub`

If you’re working from scratch in a new environment, you’ll need Python (and the repository’s Python dependencies) to run the tooling.

## EPUB Validation

EPUB validation can be accomplished with **epubcheck**.

After packaging an `.epub`, run epubcheck against the file to catch common structural and standards issues (OPF/NCX/nav consistency, missing assets, invalid markup, etc.).

```sh
brew install epubcheck

epubcheck dist/Unchanged-Translations.epub
epubcheck dist/English-Localized.epub
```

## Contributing

Contributions are welcome, especially new short stories or fixes that keep the collection consistent and EPUB-valid.

### Adding a new story

The process for adding a new story is intentionally simple:

1. Pick the track you’re contributing to:
   - `Unchanged-Translations/EPUB/` for baseline/unchanged wording.
   - `English-Localized/EPUB/` for the localized version.
2. Provide the story text to your **AI code assistant of choice** and ask it to generate a new `.xhtml` story file that follows the relevant guides:
   - `Unchanged-Translations/STYLE_GUIDE.md`
   - `Unchanged-Translations/XHTML_STRUCTURE_GUIDE.md`
   - `English-Localized/LOCALIZATION_STYLE_GUIDE.md`
   - `English-Localized/XHTML_STRUCTURE_GUIDE.md`

```text
Example AI Prompt:

Follow the Style Guide and XHTML Structure guide located in `Unchanged-Translations` to create a new story in the `Unchanged-Translations/EPUB` folder. Once the story file exists, ensure that it is added to the index and metadata files (content.opf`, `nav.xhtml`, and `toc.ncx`) after the story "Aqua Sensei". This story is titled "Some KonoSuba Story" and here is the full text:

<insert full story text>
```

3. Make sure the new XHTML file matches the established structure (metadata block, required horizontal rules, correct language attributes, etc.).
4. Regenerate `content.opf`, `nav.xhtml`, and `toc.ncx` for the target track so the TOC/manifest reflects the new story.
5. Package the EPUB and validate the output with **epubcheck**.

### What to keep in mind

- Prefer mechanical/structural fixes over rewriting content unless you’re working in the localized track.
- Keep XHTML well-formed and standards-friendly.
- Maintain consistent titles (`<title>` / `<h1>`) so navigation labels remain correct.

## Notes

This project is a personal collection + tooling exercise. If you spot missing stories, incorrect metadata, or EPUB structure issues, opening an issue (or a PR) with details is appreciated.
