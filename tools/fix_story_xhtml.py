#!/usr/bin/env python3
"""Fix mechanical XHTML issues in English-Localized story files.

Scope (intentionally narrow):
- Convert straight ASCII quotes/apostrophes in *text nodes* to Unicode curly quotes.
- Normalize metadata labels under <h1> to match XHTML_STRUCTURE_GUIDE.md:
  - Translator:
  - Editors:
  - Occurrence:
- Ensure there is a final <hr/> before </body> (when missing).
- Ensure <title> matches <h1> text (whitespace-normalized).

This avoids touching tag attributes and only lightly touches metadata lines.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


EXCLUDE = {
    "nav.xhtml",
    "cover.xhtml",
    "copyright.xhtml",
    "translators.xhtml",
}

_SKIP_TAGS = {"script", "style", "pre", "code"}


@dataclass
class QuoteState:
    double_open_next: bool = True
    single_open_next: bool = True


_ELISION_RE = re.compile(r"(^|[\s(\[{<])'(tis|twas|cause|em|til|n)(?=\b)", re.IGNORECASE)
_YEAR_ELISION_RE = re.compile(r"(^|\s)'(?=\d{2}\b)")


def _convert_text_punct(text: str, state: QuoteState) -> str:
    if not text:
        return text

    # Unicode punctuation (preferred in LOCALIZATION_STYLE_GUIDE.md)
    # Convert ASCII ellipses and multi-hyphen dashes in text nodes.
    # Convert aggressively, including styles like "...hello".
    text = text.replace("...", "…")
    text = re.sub(r"-{2,}", "—", text)

    # Common elisions -> apostrophe (not opening quote)
    text = _ELISION_RE.sub(lambda m: f"{m.group(1)}’{m.group(2)}", text)
    text = _YEAR_ELISION_RE.sub(lambda m: f"{m.group(1)}’", text)

    # Intra-word apostrophes (contractions/possessives)
    text = re.sub(r"(?<=\w)'(?=\w)", "’", text)

    out: list[str] = []
    for i, ch in enumerate(text):
        if ch == '"':
            out.append('“' if state.double_open_next else '”')
            state.double_open_next = not state.double_open_next
            continue

        if ch == "'":
            prev_c = text[i - 1] if i > 0 else ""
            next_c = text[i + 1] if i + 1 < len(text) else ""

            # If it's adjacent to word chars, treat as apostrophe (should mostly be handled already).
            if (prev_c and prev_c.isalnum()) or (next_c and next_c.isalnum()):
                out.append('’')
                continue

            out.append('‘' if state.single_open_next else '’')
            state.single_open_next = not state.single_open_next
            continue

        out.append(ch)

    return "".join(out)


_TAG_NAME_RE = re.compile(r"^</?\s*([A-Za-z][A-Za-z0-9:_-]*)")


def _split_tags(content: str) -> list[str]:
    # Split into alternating text and tag segments: [text, <tag>, text, <tag>, ...]
    return re.split(r"(<[^>]+>)", content)


def _process_text_nodes_only(content: str) -> str:
    parts = _split_tags(content)
    state = QuoteState()

    stack: list[str] = []

    for idx, part in enumerate(parts):
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            m = _TAG_NAME_RE.match(part)
            if m:
                name = m.group(1).lower()
                is_close = part.startswith("</")
                is_self = part.rstrip().endswith("/>")

                if is_close:
                    # pop last matching
                    for j in range(len(stack) - 1, -1, -1):
                        if stack[j] == name:
                            del stack[j:]
                            break
                elif not is_self:
                    stack.append(name)

            continue

        # Text node segment
        if any(tag in _SKIP_TAGS for tag in stack):
            continue

        parts[idx] = _convert_text_punct(part, state)

    return "".join(parts)


def _normalize_title_to_h1(lines: list[str]) -> bool:
    content = "\n".join(lines)

    title_m = re.search(r"(<title>)(.*?)(</title>)", content, flags=re.DOTALL | re.IGNORECASE)
    h1_m = re.search(r"(<h1>)(.*?)(</h1>)", content, flags=re.DOTALL | re.IGNORECASE)
    if not title_m or not h1_m:
        return False

    def norm(s: str) -> str:
        return " ".join(re.sub(r"<[^>]+>", "", s).split())

    title_text = title_m.group(2)
    h1_text = h1_m.group(2)

    if norm(title_text) == norm(h1_text) or not norm(h1_text):
        return False

    new_content = content[: title_m.start(2)] + h1_m.group(2) + content[title_m.end(2) :]
    if new_content == content:
        return False

    lines[:] = new_content.split("\n")
    return True


def _fix_metadata_labels(lines: list[str]) -> bool:
    changed = False

    # Find indices of <h1> ... </h1> and first <hr/> after it.
    h1_idx = next((i for i, ln in enumerate(lines) if "<h1" in ln and "</h1>" in ln), None)
    if h1_idx is None:
        return False

    hr_idx = None
    for i in range(h1_idx + 1, len(lines)):
        if "<hr" in lines[i]:
            hr_idx = i
            break
    if hr_idx is None:
        return False

    for i in range(h1_idx + 1, hr_idx):
        ln = lines[i]

        # TL / Editing patterns with emphasis
        m = re.match(r"^(\s*)<p>\s*<(?:em|i)>\s*TL\s*:\s*(.*?)\s*</(?:em|i)>\s*</p>\s*$", ln, flags=re.IGNORECASE)
        if m:
            indent, who = m.group(1), m.group(2)
            lines[i] = f"{indent}<p>Translator: {who}</p>"
            changed = True
            continue

        m = re.match(r"^(\s*)<p>\s*<(?:em|i)>\s*Editing\s*:\s*(.*?)\s*</(?:em|i)>\s*</p>\s*$", ln, flags=re.IGNORECASE)
        if m:
            indent, who = m.group(1), m.group(2)
            lines[i] = f"{indent}<p>Editors: {who}</p>"
            changed = True
            continue

        # Plain label normalization
        # Editor: -> Editors:
        ln2 = re.sub(r"(<p>\s*)Editor:\s*", r"\1Editors: ", ln, flags=re.IGNORECASE)
        # Editing: -> Editors:
        ln2 = re.sub(r"(<p>\s*)Editing:\s*", r"\1Editors: ", ln2, flags=re.IGNORECASE)
        # TL: -> Translator:
        ln2 = re.sub(r"(<p>\s*)TL:\s*", r"\1Translator: ", ln2, flags=re.IGNORECASE)
        # Translated by: -> Translator:
        ln2 = re.sub(r"(<p>\s*)Translated\s+by:\s*", r"\1Translator: ", ln2, flags=re.IGNORECASE)
        # Translation: -> Translator:
        ln2 = re.sub(r"(<p>\s*)Translation:\s*", r"\1Translator: ", ln2, flags=re.IGNORECASE)

        # Ensure required label casing/punctuation
        ln2 = re.sub(r"(<p>\s*)translator\s*:\s*", r"\1Translator: ", ln2)
        ln2 = re.sub(r"(<p>\s*)editors?\s*:\s*", r"\1Editors: ", ln2)
        ln2 = re.sub(r"(<p>\s*)occurrence\s*:\s*", r"\1Occurrence: ", ln2)

        if ln2 != ln:
            lines[i] = ln2
            changed = True

    return changed


def _insert_localization_credit(lines: list[str], credit_line: str) -> bool:
    # Insert within the metadata block (after <h1> and before the first <hr/>):
    # - After Editors: if present
    # - Else after Translator:
    # Do nothing if already present.
    h1_idx = next((i for i, ln in enumerate(lines) if "<h1" in ln and "</h1>" in ln), None)
    if h1_idx is None:
        return False

    hr_idx = None
    for i in range(h1_idx + 1, len(lines)):
        if "<hr" in lines[i]:
            hr_idx = i
            break
    if hr_idx is None:
        return False

    for i in range(h1_idx + 1, hr_idx):
        if "<p>Localization:" in lines[i]:
            return False

    editors_re = re.compile(r"^\s*<p>\s*Editors:\s*", re.IGNORECASE)
    translator_re = re.compile(r"^\s*<p>\s*Translator:\s*", re.IGNORECASE)

    insert_after = None
    indent = None
    for i in range(h1_idx + 1, hr_idx):
        if editors_re.search(lines[i]):
            insert_after = i
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]

    if insert_after is None:
        for i in range(h1_idx + 1, hr_idx):
            if translator_re.search(lines[i]):
                insert_after = i
                indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                break

    if insert_after is None:
        return False

    if indent is None:
        indent = "  "

    # Prefer inserting after any blank lines that already follow the target line
    # so we keep existing spacing style.
    j = insert_after + 1
    while j < hr_idx and lines[j].strip() == "":
        j += 1

    # If there was at least one blank line, insert just before the next content.
    # Otherwise insert immediately after the target line.
    insertion_index = j if j > insert_after + 1 else insert_after + 1
    lines[insertion_index:insertion_index] = [f"{indent}{credit_line}"]

    # Ensure there's a blank line after the inserted credit unless we're already
    # immediately followed by a blank.
    if insertion_index + 1 < len(lines) and lines[insertion_index + 1].strip() != "":
        lines[insertion_index + 1:insertion_index + 1] = [""]

    return True


def _ensure_final_hr(lines: list[str]) -> bool:
    # Insert <hr/> before </body> if the last meaningful element in <body> isn't <hr/>.
    body_close_idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().lower() == "</body>"), None)
    if body_close_idx is None:
        return False

    # Find last non-empty line before </body>
    j = body_close_idx - 1
    while j >= 0 and lines[j].strip() == "":
        j -= 1
    if j < 0:
        return False

    if lines[j].strip().lower().startswith("<hr"):
        return False

    # Determine indentation based on first <hr/> in file
    hr_indent = "  "
    for ln in lines:
        if "<hr" in ln:
            hr_indent = ln[: len(ln) - len(ln.lstrip())]
            break

    # Preserve the common pattern: blank line, indent <hr/>, blank line
    insert_at = body_close_idx
    lines[insert_at:insert_at] = ["", f"{hr_indent}<hr/>", ""]
    return True


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _iter_story_files(epub_dir: Path) -> list[Path]:
    return sorted(p for p in epub_dir.glob("*.xhtml") if p.name not in EXCLUDE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--epub-dir",
        default="English-Localized/EPUB",
        help="Directory containing the story .xhtml files (default: English-Localized/EPUB)",
    )
    ap.add_argument(
        "--add-localization-credit",
        action="store_true",
        help="Insert a Localization credit <p> line in the metadata block.",
    )
    ap.add_argument(
        "--localization-credit-line",
        default="<p>Localization: Sean92us (Utilizing GPT-5.2)</p>",
        help="Exact <p> line to insert when --add-localization-credit is set.",
    )
    ap.add_argument("--check", action="store_true", help="Only report which files would change")
    args = ap.parse_args()

    epub_dir = Path(args.epub_dir)
    if not epub_dir.exists() or not epub_dir.is_dir():
        raise SystemExit(f"epub-dir not found or not a directory: {epub_dir}")

    changed_files: list[Path] = []

    for path in _iter_story_files(epub_dir):
        original = _read_text(path)
        lines = original.split("\n")

        changed = False
        changed |= _normalize_title_to_h1(lines)
        changed |= _fix_metadata_labels(lines)
        if args.add_localization_credit:
            changed |= _insert_localization_credit(lines, args.localization_credit_line)
        changed |= _ensure_final_hr(lines)

        intermediate = "\n".join(lines)
        intermediate = _process_text_nodes_only(intermediate)

        if intermediate != original:
            changed = True

        if not changed:
            continue

        if args.check:
            changed_files.append(path)
            continue

        _write_text(path, intermediate)
        changed_files.append(path)

    print(f"changed_files {len(changed_files)}")
    for p in changed_files:
        print(p.as_posix())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
