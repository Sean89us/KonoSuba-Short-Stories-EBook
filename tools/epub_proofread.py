#!/usr/bin/env python3
"""Scan EPUB XHTML files and generate a proofreading report.

This tool is intentionally conservative: it does not try to rewrite prose.
It can optionally apply very safe, mechanical fixes (spacing around punctuation)
and will still produce a report for everything else that needs a human review.

Usage:
    python tools/epub_proofread.py --epub-dir EPUB --out proofread_report.md
    python tools/epub_proofread.py --fix --epub-dir EPUB --out proofread_report.md
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import os
import re
from pathlib import Path
from typing import Optional

from lxml import etree


@dataclasses.dataclass(frozen=True)
class Issue:
    file: Path
    line: int
    kind: str
    message: str
    snippet: str


# Space before punctuation, but do not treat ellipses like " ..." as errors.
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,;:!?])|\s+\.(?!\.)")
_MULTI_SPACE_RE = re.compile(r" {2,}")
_DUP_WORD_RE = re.compile(r"\b([A-Za-z]+)\s+\1\b", re.IGNORECASE)
_LOWER_AFTER_SENTENCE_RE = re.compile(r"[.!?]\s+[a-z]")
# Missing space after punctuation, but intentionally ignore ellipses like "...hello".
_MISSING_SPACE_AFTER_PUNCT_RE = re.compile(
    r"([,;:!?])([A-Za-z])|(?<!\.)\.([A-Za-z])"
)

_TAG_NAME_RE = re.compile(r"^</?\s*([A-Za-z][A-Za-z0-9:_-]*)")

_SKIP_TEXT_INSIDE_TAGS = {
    "script",
    "style",
    "pre",
    "code",
}

_PARAGRAPH_LIKE_TAGS = {
    "p",
    "li",
    "blockquote",
    "h1",
    "h2",
    "h3",
}


@dataclasses.dataclass(frozen=True)
class LtChange:
    file: Path
    line: int
    rule_id: str
    issue_type: str
    message: str
    before: str
    after: str


@dataclasses.dataclass(frozen=True)
class PhraseChange:
    file: Path
    line: int
    rule: str
    before: str
    after: str


_PHRASE_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "whats_is_it_you_two",
        re.compile(r"\bWhat'?s\s+is\s+it\s+you\s+two\b", re.IGNORECASE),
        "What's with you two",
    ),
    (
        "whats_is_it",
        re.compile(r"\bWhat'?s\s+is\s+it\b", re.IGNORECASE),
        "What is it",
    ),
    (
        "whats_is",
        re.compile(r"\bWhat'?s\s+is\b", re.IGNORECASE),
        "What is",
    ),
    (
        "want_you_accompany",
        re.compile(r"\bwant\s+you\s+accompany\b", re.IGNORECASE),
        "want you to accompany",
    ),
]


def _phrase_fix_text_segment(text: str) -> tuple[str, list[str]]:
    if not text or _is_whitespace_only(text):
        return text, []

    fixed = text
    applied_rules: list[str] = []

    for rule_name, pattern, replacement in _PHRASE_RULES:
        new = pattern.sub(replacement, fixed)
        if new != fixed:
            fixed = new
            applied_rules.append(rule_name)

    return fixed, applied_rules


def _iter_xhtml_files(epub_dir: Path) -> list[Path]:
    return sorted(p for p in epub_dir.rglob("*.xhtml") if p.is_file())


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _snippet(text: str, limit: int = 80) -> str:
    cleaned = _collapse_ws(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."


def _safe_int(value: Optional[int]) -> int:
    try:
        return int(value or 1)
    except Exception:
        return 1


def _is_meaningful_text(text: Optional[str]) -> bool:
    if not text:
        return False
    return _collapse_ws(text) != ""


def _is_whitespace_only(text: str) -> bool:
    return text.strip() == ""


def _push_tag(stack: list[str], tag_name: str) -> None:
    stack.append(tag_name.lower())


def _pop_tag(stack: list[str], tag_name: str) -> None:
    name = tag_name.lower()
    if not stack:
        return
    if stack[-1] == name:
        stack.pop()
        return
    # Be forgiving of minor XHTML malformations; drop back to last matching tag.
    for i in range(len(stack) - 1, -1, -1):
        if stack[i] == name:
            del stack[i:]
            return


def _in_skip_context(stack: list[str]) -> bool:
    return any(tag in _SKIP_TEXT_INSIDE_TAGS for tag in stack)


def _fix_text_segment(text: str) -> str:
    # Skip empty/whitespace-only segments (pretty-print indentation between tags).
    if not text or _is_whitespace_only(text):
        return text

    fixed = text

    # Remove spaces before punctuation: "word ," -> "word,"
    # Do NOT remove the space before an ellipsis like "I ...think".
    fixed = re.sub(r"\s+([,;:!?])", r"\1", fixed)
    fixed = re.sub(r"\s+\.(?!\.)", ".", fixed)

    # Collapse repeated spaces (but do not touch newlines/tabs).
    fixed = re.sub(r" {2,}", " ", fixed)

    # Add missing space after punctuation for the most common cases.
    fixed = re.sub(r"([,;:!?])([A-Za-z])", r"\1 \2", fixed)

    # Period is trickier due to initialisms like "U.S."; avoid adding spaces there.
    # Also avoid touching ellipses like "...hello" (awkwardness style).
    fixed = re.sub(r"(?<!\\.)(?<!\\b[A-Z])\\.([A-Za-z])", r". \\1", fixed)

    # Preserve no-space style after ellipsis when it leads into a word.
    # (The author often uses "...hello" as intentional awkwardness.)
    fixed = re.sub(r"\\.\\.\\.\\s+([A-Za-z])", r"...\\1", fixed)
    fixed = re.sub(r"...\\s+([A-Za-z])", r"...\\1", fixed)

    # If a previous run collapsed "I ...think" into "I...think", restore it.
    # Keep this intentionally narrow to avoid changing normal ellipses like "Wait...what".
    fixed = re.sub(r"\bI\\.\\.\\.([A-Za-z])", r"I ...\\1", fixed)
    fixed = re.sub(r"\bi\\.\\.\\.([A-Za-z])", r"i ...\\1", fixed)

    return fixed


def _looks_like_ellipsis_style(text: str) -> bool:
    return "..." in text or "…" in text


def _would_break_ellipsis(before: str, after: str) -> bool:
    # Protect intentional styles:
    # - "...hello" (no space)
    # - "I ...think" (space before ellipsis)
    # We don't want LT to rewrite these.
    if before == after:
        return False

    # If either side contains ellipsis tokens and they differ, be cautious.
    if ("..." in before or "..." in after) and before.replace("...", "") != after.replace(
        "...", ""
    ):
        # Still allow changes that don't alter the literal ellipsis patterns.
        return ("..." in before) != ("..." in after)

    if ("…" in before or "…" in after) and before.replace("…", "") != after.replace(
        "…", ""
    ):
        return ("…" in before) != ("…" in after)

    # Explicitly prevent these two transformations.
    if re.search(r"\.\.\.\s+[A-Za-z]", after) and re.search(r"\.\.\.[A-Za-z]", before):
        return True
    if re.search(r"\b[Ii]\.{3}[A-Za-z]", after) and re.search(
        r"\b[Ii]\s+\.{3}[A-Za-z]", before
    ):
        return True
    return False


def _lt_fix_text_segment(
    text: str, *, tool, aggressive: bool
) -> tuple[str, list[tuple[str, str, str, str]]]:
    """Apply LanguageTool suggestions.

    Returns: (fixed_text, list of (rule_id, issue_type, message, replacement_used)).
    """

    if not text or _is_whitespace_only(text):
        return text, []

    matches = tool.check(text)
    if not matches:
        return text, []

    # Apply edits from end to start to keep offsets valid.
    fixed = text
    applied: list[tuple[str, str, str, str]] = []

    def _allowed(match) -> bool:
        issue_type = getattr(match, "rule_issue_type", "") or ""
        rule_id = getattr(match, "rule_id", "") or ""
        message = getattr(match, "message", "") or ""
        replacements = getattr(match, "replacements", None) or []

        if not replacements:
            return False

        # In aggressive mode we still skip explicit style rewrites.
        if "style" in message.lower() and not aggressive:
            return False

        if issue_type in {"misspelling", "typographical"}:
            return True

        if issue_type == "whitespace":
            # Let our own spacing rules dominate around ellipses.
            if _looks_like_ellipsis_style(text):
                return False
            return True

        if issue_type == "grammar":
            # Aggressive: allow grammar fixes even with multiple replacements.
            return True if aggressive else (len(replacements) == 1)

        if issue_type in {"punctuation", "typographical"}:
            return True

        if issue_type == "style":
            # Still conservative: only apply very simple style changes.
            return aggressive and len(replacements) == 1

        # Unknown types: skip.
        return False

    for match in sorted(matches, key=lambda m: m.offset, reverse=True):
        if not _allowed(match):
            continue

        offset = int(match.offset)
        length = int(getattr(match, "error_length", 0))
        before = fixed[offset : offset + length]
        # Prefer the first suggestion (LT orders by likelihood).
        replacement = (match.replacements[0] if match.replacements else "")
        if not replacement:
            continue

        issue_type = getattr(match, "rule_issue_type", "") or ""

        # Protect proper nouns / names.
        if issue_type in {"misspelling", "typographical"} and re.search(r"[A-Z]", before):
            continue

        # Avoid hyphenation/compounding style changes like "faceplant" -> "face-plant".
        # (Even in aggressive mode, this tends to damage proper nouns / voice.)
        if issue_type in {"misspelling", "typographical"} and re.search(r"[-\s]", replacement):
            continue

        # Avoid turning non-English/fantasy terms into common English words.
        # Only accept spelling fixes when the replacement is very similar to the original
        # (or it only adds/removes apostrophes).
        if issue_type in {"misspelling", "typographical"}:
            before_clean = re.sub(r"[^A-Za-z']", "", before).lower()
            after_clean = re.sub(r"[^A-Za-z']", "", replacement).lower()
            if not before_clean or not after_clean:
                continue

            # Apostrophe-only adjustments like "dont" -> "don't".
            if before_clean.replace("'", "") == after_clean.replace("'", "") and (
                ("'" in before_clean) != ("'" in after_clean)
            ):
                pass
            else:
                ratio = difflib.SequenceMatcher(a=before_clean, b=after_clean).ratio()
                if ratio < 0.88:
                    continue

        after = replacement

        # Ellipsis protection.
        if _would_break_ellipsis(before, after):
            continue

        fixed = fixed[:offset] + after + fixed[offset + length :]
        applied.append(
            (
                getattr(match, "rule_id", ""),
                getattr(match, "rule_issue_type", ""),
                getattr(match, "message", ""),
                replacement,
            )
        )

    return fixed, list(reversed(applied))


def _prepend_preserving_indent(text: str, prefix: str) -> str:
    m = re.match(r"\s*", text)
    lead = m.group(0) if m else ""
    return lead + prefix + text[len(lead) :]


def _append_preserving_trailing_ws(text: str, suffix: str) -> str:
    m = re.match(r"(?s)(.*?)(\s*)\Z", text)
    if not m:
        return text + suffix
    body, tail = m.group(1), m.group(2)
    return body + suffix + tail


def _maybe_fix_unbalanced_quotes_in_paragraph(
    *,
    parts: list[str],
    first_text_index: Optional[int],
    last_text_index: Optional[int],
    straight_quotes: int,
    open_curly: int,
    close_curly: int,
    start_sample: str,
    end_sample: str,
) -> bool:
    """Fix quotes when the paragraph is off by exactly one.

    This is conservative by design:
    - Only fixes when the paragraph uses exclusively straight OR exclusively curly quotes.
    - Only fixes when the imbalance is exactly 1.
    - Inserts at the start/end of the paragraph (first/last meaningful text segment).
    """

    if first_text_index is None or last_text_index is None:
        return False

    uses_straight = straight_quotes > 0
    uses_curly = (open_curly + close_curly) > 0
    if uses_straight and uses_curly:
        return False

    start_trim = start_sample.lstrip()
    end_trim = end_sample.rstrip()

    # Straight quotes
    if uses_straight and straight_quotes % 2 == 1:
        starts_with = start_trim.startswith('"')
        ends_with = end_trim.endswith('"')
        if starts_with and not ends_with:
            parts[last_text_index] = _append_preserving_trailing_ws(
                parts[last_text_index], '"'
            )
            return True
        if ends_with and not starts_with:
            parts[first_text_index] = _prepend_preserving_indent(
                parts[first_text_index], '"'
            )
            return True
        parts[last_text_index] = _append_preserving_trailing_ws(
            parts[last_text_index], '"'
        )
        return True

    # Curly quotes
    if uses_curly:
        diff = open_curly - close_curly
        if diff == 1:
            if not end_trim.endswith("”"):
                parts[last_text_index] = _append_preserving_trailing_ws(
                    parts[last_text_index], "”"
                )
                return True
        elif diff == -1:
            if not start_trim.startswith("“"):
                parts[first_text_index] = _prepend_preserving_indent(
                    parts[first_text_index], "“"
                )
                return True

    return False


def fix_file_in_place(
    path: Path,
    *,
    lt_tool=None,
    lt_fix: bool = False,
    lt_changes: Optional[list[LtChange]] = None,
    lt_aggressive: bool = False,
    phrase_fix: bool = False,
    phrase_changes: Optional[list[PhraseChange]] = None,
) -> int:
    """Apply conservative mechanical fixes to text segments only.

    Returns the number of changed text segments.
    """

    original = path.read_text(encoding="utf-8")
    parts = re.split(r"(<[^>]+>)", original)
    stack: list[str] = []
    changed_segments = 0
    current_line = 1

    # Track paragraph-like scope so we can fix unbalanced quotes without parsing/rewriting XHTML.
    para_stack: list[dict[str, object]] = []

    for i, part in enumerate(parts):
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            # Track a minimal tag stack so we can avoid touching <pre>, <code>, etc.
            if part.startswith("<!--") or part.startswith("<!") or part.startswith("<?"):
                continue

            is_end = part.startswith("</")
            is_self_closing = part.rstrip().endswith("/>")
            m = _TAG_NAME_RE.match(part)
            if not m:
                continue
            tag = m.group(1)

            if is_end:
                # Close paragraph-like scope first (so the closing tag isn't inside it).
                if tag.lower() in _PARAGRAPH_LIKE_TAGS and para_stack:
                    ctx = para_stack[-1]
                    if ctx.get("tag") == tag.lower():
                        para_stack.pop()
                        fixed = _maybe_fix_unbalanced_quotes_in_paragraph(
                            parts=parts,
                            first_text_index=ctx.get("first_text_index"),
                            last_text_index=ctx.get("last_text_index"),
                            straight_quotes=int(ctx.get("straight_quotes", 0)),
                            open_curly=int(ctx.get("open_curly", 0)),
                            close_curly=int(ctx.get("close_curly", 0)),
                            start_sample=str(ctx.get("start_sample", "")),
                            end_sample=str(ctx.get("end_sample", "")),
                        )
                        if fixed:
                            changed_segments += 1

                _pop_tag(stack, tag)
            else:
                if not is_self_closing:
                    _push_tag(stack, tag)
                    if tag.lower() in _PARAGRAPH_LIKE_TAGS:
                        para_stack.append(
                            {
                                "tag": tag.lower(),
                                "first_text_index": None,
                                "last_text_index": None,
                                "straight_quotes": 0,
                                "open_curly": 0,
                                "close_curly": 0,
                                "start_sample": "",
                                "end_sample": "",
                            }
                        )
            continue

        # Text segment
        if _in_skip_context(stack):
            current_line += part.count("\n")
            continue

        segment_line = current_line

        if phrase_fix:
            phrase_fixed, phrase_rules = _phrase_fix_text_segment(part)
            if phrase_fixed != part:
                if phrase_changes is not None:
                    before_snip = _snippet(part)
                    after_snip = _snippet(phrase_fixed)
                    for rule in phrase_rules:
                        phrase_changes.append(
                            PhraseChange(
                                file=path,
                                line=segment_line,
                                rule=rule,
                                before=before_snip,
                                after=after_snip,
                            )
                        )
                parts[i] = phrase_fixed
                part = phrase_fixed
                changed_segments += 1

        if lt_fix and lt_tool is not None:
            fixed_lt, applied = _lt_fix_text_segment(
                part, tool=lt_tool, aggressive=lt_aggressive
            )
            if fixed_lt != part:
                if lt_changes is not None and applied:
                    before_snip = _snippet(part)
                    after_snip = _snippet(fixed_lt)
                    for rule_id, issue_type, message, _replacement in applied:
                        lt_changes.append(
                            LtChange(
                                file=path,
                                line=segment_line,
                                rule_id=str(rule_id),
                                issue_type=str(issue_type),
                                message=str(message),
                                before=before_snip,
                                after=after_snip,
                            )
                        )
                parts[i] = fixed_lt
                part = fixed_lt
                changed_segments += 1

        if para_stack and _is_meaningful_text(part):
            ctx = para_stack[-1]
            ctx["straight_quotes"] = int(ctx.get("straight_quotes", 0)) + part.count('"')
            ctx["open_curly"] = int(ctx.get("open_curly", 0)) + part.count("“")
            ctx["close_curly"] = int(ctx.get("close_curly", 0)) + part.count("”")

            if ctx.get("first_text_index") is None:
                ctx["first_text_index"] = i
                ctx["start_sample"] = part
            ctx["last_text_index"] = i
            ctx["end_sample"] = part

        fixed = _fix_text_segment(part)
        if fixed != part:
            parts[i] = fixed
            changed_segments += 1

        current_line += part.count("\n")

    if changed_segments:
        path.write_text("".join(parts), encoding="utf-8")

    return changed_segments


def _full_text(element: etree._Element) -> str:
    parts: list[str] = []
    for t in element.itertext():
        if t:
            parts.append(t)
    return "".join(parts)


def _analyze_text_segment(
    *,
    file: Path,
    line: int,
    text: str,
    issues: list[Issue],
) -> None:
    if _MULTI_SPACE_RE.search(text):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Spacing",
                message="Multiple consecutive spaces",
                snippet=_snippet(text),
            )
        )

    if _SPACE_BEFORE_PUNCT_RE.search(text):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Punctuation",
                message="Space before punctuation (e.g., 'word ,')",
                snippet=_snippet(text),
            )
        )

    if _DUP_WORD_RE.search(text):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="DupWord",
                message="Possible duplicated word",
                snippet=_snippet(text),
            )
        )

    if _LOWER_AFTER_SENTENCE_RE.search(text):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Capitalization",
                message="Lowercase letter after sentence-ending punctuation",
                snippet=_snippet(text),
            )
        )

    if _MISSING_SPACE_AFTER_PUNCT_RE.search(text):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Punctuation",
                message="Possible missing space after punctuation (e.g., 'word,Next' or 'Mr.Smith')",
                snippet=_snippet(text),
            )
        )


def _analyze_paragraph_like(
    *,
    file: Path,
    element: etree._Element,
    issues: list[Issue],
) -> None:
    text = _full_text(element)
    if not _is_meaningful_text(text):
        return

    line = _safe_int(getattr(element, "sourceline", None))

    straight_quotes = text.count('"')
    open_curly = text.count("“")
    close_curly = text.count("”")

    if straight_quotes % 2 == 1:
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Quotes",
                message='Unbalanced straight quotes (") in paragraph',
                snippet=_snippet(text),
            )
        )

    if open_curly != close_curly:
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Quotes",
                message="Unbalanced curly quotes (“ ”) in paragraph",
                snippet=_snippet(text),
            )
        )

    if straight_quotes and (open_curly or close_curly):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Quotes",
                message="Mixed straight and curly quotes in paragraph",
                snippet=_snippet(text),
            )
        )

    if text.count("(") != text.count(")"):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Balance",
                message="Unbalanced parentheses in paragraph",
                snippet=_snippet(text),
            )
        )

    if text.count("[") != text.count("]"):
        issues.append(
            Issue(
                file=file,
                line=line,
                kind="Balance",
                message="Unbalanced brackets in paragraph",
                snippet=_snippet(text),
            )
        )

    trimmed = _collapse_ws(text)
    if len(trimmed) >= 40:
        if re.search(r"[A-Za-z0-9]$", trimmed) and not re.search(
            r"[.!?...]$", trimmed
        ):
            issues.append(
                Issue(
                    file=file,
                    line=line,
                    kind="Punctuation",
                    message="Paragraph may be missing ending punctuation",
                    snippet=_snippet(text),
                )
            )


def scan_file(
    path: Path,
    *,
    fix: bool = False,
    lt_tool=None,
    lt_fix: bool = False,
    lt_changes: Optional[list[LtChange]] = None,
    lt_aggressive: bool = False,
    phrase_fix: bool = False,
    phrase_changes: Optional[list[PhraseChange]] = None,
) -> tuple[list[Issue], int]:
    changed_segments = 0
    if fix:
        changed_segments = fix_file_in_place(
            path,
            lt_tool=lt_tool,
            lt_fix=lt_fix,
            lt_changes=lt_changes,
            lt_aggressive=lt_aggressive,
            phrase_fix=phrase_fix,
            phrase_changes=phrase_changes,
        )

    parser = etree.XMLParser(
        recover=True,
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
        remove_blank_text=False,
    )

    try:
        tree = etree.parse(str(path), parser)
    except Exception as exc:
        return (
            [
            Issue(
                file=path,
                line=1,
                kind="Parse",
                message=f"Failed to parse XHTML: {type(exc).__name__}: {exc}",
                snippet="",
            )
            ],
            changed_segments,
        )

    root = tree.getroot()

    issues: list[Issue] = []

    # Paragraph-like structural checks
    for tag in ("p", "h1", "h2", "h3", "li", "blockquote"):
        for element in root.iter():
            if etree.QName(element).localname == tag:
                _analyze_paragraph_like(file=path, element=element, issues=issues)

    # Segment-level text checks on element.text / element.tail
    for element in root.iter():
        local = etree.QName(element).localname
        if local in {"script", "style"}:
            continue

        line = _safe_int(getattr(element, "sourceline", None))

        if _is_meaningful_text(element.text):
            _analyze_text_segment(
                file=path, line=line, text=element.text or "", issues=issues
            )

        if _is_meaningful_text(element.tail):
            _analyze_text_segment(
                file=path, line=line, text=element.tail or "", issues=issues
            )

    # De-dup identical issues (common with nested text nodes)
    unique: dict[tuple[str, int, str, str], Issue] = {}
    for issue in issues:
        key = (str(issue.file), issue.line, issue.kind, issue.message)
        unique.setdefault(key, issue)

    return (
        sorted(unique.values(), key=lambda i: (str(i.file), i.line, i.kind, i.message)),
        changed_segments,
    )


def _md_link(file: Path, line: int) -> str:
    rel = file.as_posix()
    return f"[{rel}](%s#L{line})" % rel


def write_report(out_path: Path, issues: list[Issue]) -> None:
    by_file: dict[Path, list[Issue]] = {}
    for issue in issues:
        by_file.setdefault(issue.file, []).append(issue)

    lines: list[str] = []
    lines.append("# Proofreading report")
    lines.append("")
    lines.append(f"Total issues flagged: **{len(issues)}**")
    lines.append("")
    lines.append("> Notes: This is a heuristic scan, so expect false positives (especially for stylized dialogue, ellipses, and names).")
    lines.append("")

    for file in sorted(by_file.keys()):
        file_issues = by_file[file]
        rel = file.as_posix()
        lines.append(f"## {rel}")
        lines.append("")
        for issue in file_issues:
            link = _md_link(file, issue.line)
            snippet = issue.snippet.replace("\n", " ")
            if snippet:
                lines.append(f"- {link} — **{issue.kind}**: {issue.message} — _{snippet}_")
            else:
                lines.append(f"- {link} — **{issue.kind}**: {issue.message}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_languagetool_report(out_path: Path, changes: list[LtChange]) -> None:
    if not changes:
        out_path.write_text("# LanguageTool fixes\n\nNo LanguageTool fixes were applied.\n", encoding="utf-8")
        return

    lines: list[str] = []
    lines.append("# LanguageTool fixes")
    lines.append("")
    lines.append(f"Total changes applied: **{len(changes)}**")
    lines.append("")
    lines.append("> Notes: Only a conservative subset of LanguageTool suggestions were applied automatically.")
    lines.append("")

    for ch in changes:
        rel = ch.file.as_posix()
        link = f"[{rel}]({rel}#L{ch.line})"
        lines.append(
            f"- {link} — **{ch.issue_type}** `{ch.rule_id}`: {ch.message} — _{ch.before}_ → _{ch.after}_"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_phrase_report(out_path: Path, changes: list[PhraseChange]) -> None:
    if not changes:
        out_path.write_text("# Phrase fixes\n\nNo phrase fixes were applied.\n", encoding="utf-8")
        return

    lines: list[str] = []
    lines.append("# Phrase fixes")
    lines.append("")
    lines.append(f"Total changes applied: **{len(changes)}**")
    lines.append("")
    lines.append("> Notes: These are rule-based, high-confidence phrasing fixes.")
    lines.append("")
    for ch in changes:
        rel = ch.file.as_posix()
        link = f"[{rel}]({rel}#L{ch.line})"
        lines.append(f"- {link} — `{ch.rule}` — _{ch.before}_ → _{ch.after}_")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan EPUB XHTML files for common proofreading issues.")
    parser.add_argument("--epub-dir", type=Path, default=Path("EPUB"), help="Path to EPUB content directory")
    parser.add_argument("--out", type=Path, default=Path("proofread_report.md"), help="Output markdown report")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply conservative mechanical fixes in-place before reporting",
    )
    parser.add_argument(
        "--lt-fix",
        action="store_true",
        help="Also apply conservative LanguageTool fixes (requires Java) during --fix",
    )
    parser.add_argument(
        "--lt-aggressive",
        action="store_true",
        help="When used with --lt-fix, apply more aggressive grammar/punctuation fixes",
    )
    parser.add_argument(
        "--phrase-fix",
        action="store_true",
        help="Apply a small set of high-confidence phrasing/missing-word fixes during --fix",
    )
    parser.add_argument(
        "--lt-report",
        type=Path,
        default=Path("languagetool_report.md"),
        help="Where to write a report of applied LanguageTool changes",
    )
    parser.add_argument(
        "--phrase-report",
        type=Path,
        default=Path("phrase_report.md"),
        help="Where to write a report of applied phrase-rule changes",
    )
    args = parser.parse_args(argv)

    epub_dir: Path = args.epub_dir
    out_path: Path = args.out

    if not epub_dir.exists() or not epub_dir.is_dir():
        raise SystemExit(f"EPUB directory not found: {epub_dir}")

    xhtml_files = _iter_xhtml_files(epub_dir)
    all_issues: list[Issue] = []
    total_changed_segments = 0

    lt_tool = None
    lt_changes: list[LtChange] = []
    phrase_changes: list[PhraseChange] = []
    if args.lt_fix:
        if not args.fix:
            raise SystemExit("--lt-fix must be used together with --fix")
        try:
            import language_tool_python  # type: ignore
        except Exception as exc:
            raise SystemExit(f"language-tool-python not available: {exc}")
        lt_tool = language_tool_python.LanguageTool("en-US")

    for path in xhtml_files:
        issues, changed_segments = scan_file(
            path,
            fix=args.fix,
            lt_tool=lt_tool,
            lt_fix=args.lt_fix,
            lt_changes=lt_changes,
            lt_aggressive=args.lt_aggressive,
            phrase_fix=args.phrase_fix,
            phrase_changes=phrase_changes,
        )
        total_changed_segments += changed_segments
        all_issues.extend(issues)

    if lt_tool is not None:
        try:
            lt_tool.close()
        except Exception:
            pass

    write_report(out_path, all_issues)
    if args.lt_fix:
        write_languagetool_report(args.lt_report, lt_changes)
    if args.fix and args.phrase_fix:
        write_phrase_report(args.phrase_report, phrase_changes)
    if args.fix:
        print(
            f"Applied fixes to {total_changed_segments} text segments across {len(xhtml_files)} files"
        )
    print(f"Wrote report: {out_path} ({len(all_issues)} issues across {len(xhtml_files)} files)")
    if args.lt_fix:
        print(f"Wrote LanguageTool report: {args.lt_report} ({len(lt_changes)} changes)")
    if args.fix and args.phrase_fix:
        print(f"Wrote phrase report: {args.phrase_report} ({len(phrase_changes)} changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
