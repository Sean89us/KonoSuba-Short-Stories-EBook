# Translated Stories Style Guide (EPUB XHTML)

This guide documents the **specific types of edits we’ve been applying** to the story XHTML files so far.

## Goals

- Don't alter dialogue and wording choices too much. These are literal translations and the goal is to keep them in tact as much as possible, while correcting spelling, grammar, puctuation, emphasis, and file formatting.

## UK English Preference

When there’s a choice, prefer **UK English spelling, grammar, and punctuation**.

Examples (not exhaustive):

- “colour” over “color”
- “centre” over “center”
- “analyse” over “analyze”

## Hard Constraints (Do Not Break)

- Keep the document **well-formed XML/XHTML**.
  - Nothing may appear before the XML prolog line `<?xml version='1.0' encoding='utf-8'?>`.
- Preserve the overall structure:
  - stay consistent with the xhtml structure guide
  - do not add/remove sections or reorder paragraphs unless strictly necessary for grammar.
- Don’t introduce invalid nesting or unescaped characters.
  - In particular, avoid quote patterns that confuse attribute parsing or entity parsing.

## Change Types We’ve Been Making

### 1) Vanir “Moi/moi” References

Some translations render Vanir’s self-reference as `Moi` / `moi`. This is not a typo or mis-spelling.

Principle: leave `Moi/moi` as a foreign flourish. Do not change or rewrite.

### 2) Punctuation, Rhythm, and Readability

**Unicode punctuation (preferred)**

- Prefer Unicode punctuation characters over ASCII stand-ins for consistency and typography in EPUB:
  - Ellipsis: `…` (U+2026) instead of `...` when possible.
  - Em dash: `—` (U+2014) instead of `--` or a hyphen used as a dash.
  - Quotation marks (curly quotes):
    - Double: `“` (U+201C) and `”` (U+201D) instead of straight `"`.
    - Single: `‘` (U+2018) and `’` (U+2019) instead of straight `'`.
- If ASCII punctuation is found in a story file, prefer updating it to Unicode punctuation rather than leaving it as-is, so we can maintain consistency across the entire book.

**Aggressive quote conversion (preferred)**

- In story prose/dialogue, **use curly quotes aggressively**:
  - Convert straight dialogue quotes `"..."` → `“...”`.
  - Convert straight apostrophes in contractions/possessives (`don't`, `Kazuma's`) to `’`.
- Treat straight quotes as a technical/markup convenience, not a prose style.
  - Straight quotes are still expected inside XHTML markup attributes like `<p class="...">`.
  - Don’t mass-replace quotes blindly across a file unless you’re sure you’re only touching text nodes.

**Em dashes**

- Replace `-` used as an em dash with `—` (em dash character) when it’s clearly intended as a dash.
- Spacing convention (preferred): put spaces *outside* an em-dash interruption, but no spaces between the dash and the interrupted clause.
  - Example: `my sword—I don't even have the wire I used for Bind—but I` → `my sword —I don't even have the wire I used for Bind— but I`
  - Quick pattern:
    - Preferred: `word —interruption— word`
    - Avoid: `word—interruption—word` (no outside spaces)
    - Avoid: `word — interruption — word` (spaces inside the interruption)
- Use sparingly to maintain comedic timing and internal narration.

**Ellipses**

- Use `…` where it conveys timing/awkwardness; avoid overuse.

**Commas & sentence boundaries**

- Break run-ons into shorter sentences.
- Remove duplicated punctuation (e.g., `..`).

### 3) Quote Safety in XHTML

Dialogue in paragraph text should use **curly (Unicode) quotes** by default.

Rules we follow:

- **Prefer curly quotes everywhere in prose.** Convert straight to curly quotes for consistency. If you touch a file that uses straight quotes, strongly prefer converting the entire story to curly quotes rather than leaving it mixed.
- **Be consistent within a story file.** Don’t mix straight and curly quotes in the same chapter.
- **Avoid ambiguous nesting.** If a spoken line contains a quoted phrase, use single quotes inside double quotes.
  - Curly style example: `“He wrote ‘…’ on the wall.”`

- **XHTML safety:** quotes inside text nodes are safe; problems usually come from accidentally changing quotes inside tag attributes. Avoid edits that touch markup like `<p class="...">` or `<img alt="..."/>` unless necessary.

### 4) Titles and Headings

- When a file’s title reads like an unedited sentence-case fragment, we’ve sometimes normalized to **Title Case** for both `<title>` and `<h1>`.
- Keep meaning identical; don’t invent new subtitles.

### 5) Light Copyediting / Consistency

- Fix obvious typos (“maked” → “made”).
- Prefer consistent hyphenation when it improves readability:
  - “muscle-bound”, “expensive-looking”.
- Keep established in-world skill/spell names as-is (e.g., `Freeze`, `Foresight`, `Snipe`, `Lurk`, `Drain Touch`).

## What We Avoid

- No new jokes, lore changes, or added exposition.
- No “modern meme” phrasing unless it already exists in the text.
- No changes that alter plot logic or character intent.
- No structure edits that risk EPUB validity.

## QA Checklist (Per File)

After editing a file:

1. **Diagnostics check**: confirm the editor reports no errors.
2. **Top-of-file sanity**:
   - ensure the XML prolog is still the first line,
   - ensure no stray `<p>` or text got inserted above it.

## Notes on Workflow

- Prefer **smaller, context-accurate patches** over huge replacements to avoid mismatches and accidental corruption.
- If a patch fails due to “invalid context,” re-read the exact current paragraph text and retry in smaller chunks.