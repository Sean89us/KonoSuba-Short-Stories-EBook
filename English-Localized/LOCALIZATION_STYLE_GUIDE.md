# English Localization Style Guide (EPUB XHTML)

This guide documents the **specific types of edits we’ve been applying** to the story XHTML files so far.

## Goals

- Make the prose read like **native, modern English** (not “translation English”).
- Remove **honorifics** and other overt Japanese address markers.
- Reduce **JP-isms** and overly literal phrasing while preserving:
  - meaning and jokes,
  - character voice,
  - scene pacing,
  - **XHTML structure and validity**.

## US English Preference

When there’s a choice, prefer **US English spelling, grammar, and punctuation**.

Examples (not exhaustive):

- “color” over “colour”
- “center” over “centre”
- “analyze” over “analyse”
- Double quotes for dialogue (as currently used), with punctuation inside the quotes in standard US style when applicable.

## Hard Constraints (Do Not Break)

- Keep the document **well-formed XML/XHTML**.
  - Nothing may appear before the XML prolog line `<?xml version='1.0' encoding='utf-8'?>`.
- Preserve the overall structure:
  - keep existing `<h1>`, `<p>`, `<hr/>`, `<img/>`, etc.
  - do not add/remove sections or reorder paragraphs unless strictly necessary for grammar.
- Don’t introduce invalid nesting or unescaped characters.
  - In particular, avoid quote patterns that confuse attribute parsing or entity parsing.

## Change Types We’ve Been Making

### 1) Honorific & Address-Term Removal

**Remove:** `-san`, `-sama`, `-chan`, `senpai`, `sensei`, `onee-chan`, etc.

**Typical replacements** (choose the simplest, most natural option):

- `Name-san` → `Name`
- `Aqua-sama` → `Aqua` (or **Lady Aqua** only if the context is explicitly formal/religious)
- `Name-senpai` → `Teacher Name`
- `Onee-chan` / `Onee-san` → `Big Sis` / `Big Sister` / `Miss` / name (context-dependent)

**Principle:** don’t add extra formality if the original was casual—just remove the marker.

### 2) De-JP-ism / Cultural Localization

We remove or soften terms that read like imported fandom/translation jargon.

Examples of patterns to alter or remove (not exhaustive):

- `ojou-sama` → “young lady” (or “lady” depending on tone)

Some words / patterns have become common in English light novels. These should be preserved rather than altered.

Examples of words / patterns to keep (not exhaustive):

Genres/Themes: Anime, Manga, Isekai (another world), Mecha (robots), Tokusatsu (live-action, special effects).
Food/Drink: Ramen, Sushi, Sashimi, Matcha, Wasabi, Sake, Gyoza, Edamame.
Archetypes & Tropes: Loli (young-looking girl), Tsundere (harsh exterior/soft interior), Yandere (loving/violent), Megane (glasses-wearing character).
Cultural & Daily Life: Bento (boxed lunch), Katana (sword), Kimono (traditional clothing), Futon (bedding), Kotatsu (heated table), Tsunami (tidal wave), Haiku (poem), Komorebi (sunlight through trees).

Other common, untranslated words include baka (idiot), chibi (small/cute), dojo (training hall), and yokai (supernatural monster). 

These words are usually kept to preserve the cultural context, nuance, or specific sub-genre feel that direct translation would lose.

**Keep** world-specific proper nouns when they’re canon and understood (e.g., place names, spell names). If a term is unfamiliar but important, we’ve used **light inline clarification once** (e.g., “heated table (kotatsu)”).

### 3) Idiomatic Rewrite (Natural English)

We frequently rewrite sentences that are:

- overly literal (“I can’t help but…”, “as of late”, “it seems like…”) repeated too often,
- redundant,
- stiff or unnatural,
- missing native cadence.

Common transformations:

- Reduce repetition of hedges:
  - “It seems like…” → remove when obvious.
- Replace clunky exposition with tighter phrasing:
  - “On top of awarding more money in general…” → “They usually pay better…”
- Improve conversational dialogue:
  - favor contractions when voice fits (`I’d`, `we’re`, `isn’t`),
  - keep punchlines short.

### 3.25) Canon Terms & In-World Naming Consistency

Some older/rougher translations (or mixed sources) use multiple English renderings for the same in-world concept. When we encounter that, we normalize to the most **canon / commonly established** term so the collection reads consistently.

Principles:

- Prefer the established series term over a literal or overly formal rendering.
- Keep the meaning the same; this is a **terminology normalization**, not a lore edit.
- Be consistent within a file, and ideally across the entire EPUB.
- Don’t “over-normalize” unique phrasing that’s clearly deliberate characterization or a one-off joke.

Common examples we’ve been applying:

- `Crimson Magic Clansmen` / `Crimson Magic Clan` → `Crimson Demons` (people) / `Crimson Demon` (as an adjective where natural)
  - Example: “the wise Crimson Magic Clansmen” → “the wise Crimson Demons”
- `Demon king` (inconsistent casing) → `Demon King` when used as the title (to match common usage)

Mini glossary (common normalizations):

- `Crimson Magic Clan` / `Crimson Magic Clansmen` → `Crimson Demons`
- `Crimson Demon Village` (preferred as the place name; avoid alternating with “Crimson Demon clan village” unless the sentence truly calls for it)
- `Demon King` (title case when it’s the title/role; keep lower-case when it’s clearly generic)
- `Giant Frog` -> `Giant Toad` (In western KonoSuba media, the creatures known as Giant Frogs have been changed to Giant Toads instead) (This also applies to their meat, e.g. `frog meat` -> `toad meat`)
- `Axis Church` / `Eris Church` (title case for the organization name)

What not to change:

- Keep established proper nouns and skill/spell names as they appear when they’re already consistent and understood (e.g., `Explosion`, `Freeze`, `Drain Touch`, place names).
- Don’t rename labels/organizations in metadata blocks or structural text (those rules live in `XHTML_STRUCTURE_GUIDE.md`).

### 3.35) Name Changes (Spelling Normalization)

Some sources use inconsistent romanization/spelling for character names. When we encounter those variants, normalize them to a single preferred spelling for consistency across the EPUB.

Known normalizations:

- `Bukkoroli` → `Bukkororii`

Notes:

- Apply in story prose/dialogue (and headings/titles if applicable), but **do not** rename filenames/links.
- Prefer consistency across the entire `English-Localized/EPUB` set once a spelling is chosen.

### 3.36) Name Order (JP → EN)

In Japanese text (and many direct translations), personal names often appear in **family-name first** order. For English localization, flip to **given-name first** order in narrative prose and dialogue.

Examples:

- `Satou Kazuma` → `Kazuma Satou`
- `Dustiness Ford Lalatina` → `Lalatina Ford Dustiness`

Guidelines:

- Apply this when the text is clearly presenting a full personal name in JP order.
- Preserve middle/house components; just move the given name to the front.
- Don’t change names that are already in natural English order, single-name characters, or established English-canon renderings.
- As with spelling normalization: update prose/dialogue/headings as needed, but **do not** rename filenames/links.

### 3.5) Vanir “Moi/moi” References

Some translations render Vanir’s self-reference as `Moi` / `moi`. This can be ambiguous: sometimes it’s effectively a **first-person pronoun**, and sometimes it’s used to **name/identify Vanir**.

Guideline (context-dependent):

- If Vanir is speaking and `Moi/moi` is being used as first person, localize it to natural English pronouns:
  - `Moi told you already` → `I told you already` / `I’ve told you already`
  - `Moi will do Moi best` → `I’ll do my best`
  - `As Moi continued…` → `As I continued…`
- If the intent is to explicitly identify the character (or it’s part of a fixed title/appositive), use **Vanir** (or **I, Vanir, …**) rather than leaving `Moi` in place:
  - `Moi, the Archduke of Hell, …` → `I, Vanir, the Archduke of Hell, …`
  - `find Moi` (meaning “find Vanir”) → `find Vanir` / `come find me` (choose based on POV)

Principle: don’t leave `Moi/moi` as a foreign flourish in otherwise-localized English; rewrite to `Vanir` or `I/me/my/myself` depending on what reads most naturally in context.

### 4) Punctuation, Rhythm, and Readability

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

### 5) Quote Safety in XHTML

Dialogue in paragraph text should use **curly (Unicode) quotes** by default.

Rules we follow:

- **Prefer curly quotes everywhere in prose.** Convert straight to curly quotes for consistency. If you touch a file that uses straight quotes, strongly prefer converting the entire story to curly quotes rather than leaving it mixed.
- **Be consistent within a story file.** Don’t mix straight and curly quotes in the same chapter.
- **Avoid ambiguous nesting.** If a spoken line contains a quoted phrase, use single quotes inside double quotes.
  - Curly style example: `“He wrote ‘…’ on the wall.”`

- **XHTML safety:** quotes inside text nodes are safe; problems usually come from accidentally changing quotes inside tag attributes. Avoid edits that touch markup like `<p class="...">` or `<img alt="..."/>` unless necessary.

### 6) Titles and Headings

- When a file’s title reads like an unedited sentence-case fragment, we’ve sometimes normalized to **Title Case** for both `<title>` and `<h1>`.
- Keep meaning identical; don’t invent new subtitles.

### 7) Light Copyediting / Consistency

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
2. **Honorific sweep**: search for common patterns:
   - `-san`, `-sama`, `-chan`, `onee-chan`, `onee-san`, `sensei`, `senpai`, `ojou-sama`
3. **Vanir “Moi” sweep (as applicable)**:
  - search for `Moi` / `moi` and rewrite to `Vanir` or `I/me/my/myself` depending on context.
4. **Top-of-file sanity**:
   - ensure the XML prolog is still the first line,
   - ensure no stray `<p>` or text got inserted above it.

## Notes on Workflow

- Prefer **smaller, context-accurate patches** over huge replacements to avoid mismatches and accidental corruption.
- If a patch fails due to “invalid context,” re-read the exact current paragraph text and retry in smaller chunks.