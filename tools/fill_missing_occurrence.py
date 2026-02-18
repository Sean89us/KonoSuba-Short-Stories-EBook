#!/usr/bin/env python3
"""Fill missing Occurrence metadata in English-Localized story XHTML files.

Some story files contain timeline context only as a bracketed note (e.g. "around volume 4")
(or are explicitly non-canon like fanfic). This script adds a canonical metadata line:

  <p>Occurrence: ...</p>

Insertion location: within the metadata block (after <h1>, before first <hr/>),
preferably after Editors: when present, otherwise after Translator:.

This script is intentionally conservative and only edits files that:
- are in English-Localized/EPUB
- are .xhtml
- are not navigation/cover/copyright/translators
- do not already contain an Occurrence: line.

Usage:
  python tools/fill_missing_occurrence.py --epub-dir English-Localized/EPUB

Exit codes:
  0 success
  2 invalid arguments
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


XHTML_NS = "http://www.w3.org/1999/xhtml"
NS = {"xhtml": XHTML_NS}

EXCLUDE = {
    "nav.xhtml",
    "cover.xhtml",
    "copyright.xhtml",
    "translators.xhtml",
    "toc.ncx",
}


@dataclass(frozen=True)
class Change:
    path: Path
    occurrence: str


_VOL_RANGE_RE = re.compile(
    r"\bvol(?:ume)?s?\s*(\d+)\s*(?:[-–—]|to|through)\s*(\d+)\b", re.IGNORECASE
)
_VOL_SINGLE_RE = re.compile(r"\bvol(?:ume)?\s*(\d+)\b", re.IGNORECASE)


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def _read_xml(path: Path) -> etree._ElementTree:
    parser = etree.XMLParser(resolve_entities=False, recover=False, remove_blank_text=False)
    return etree.parse(str(path), parser)


def _metadata_children(body: etree._Element) -> tuple[list[etree._Element], int, int]:
    children = [c for c in body if isinstance(c.tag, str)]
    h1_index = next((i for i, c in enumerate(children) if c.tag == f"{{{XHTML_NS}}}h1"), None)
    if h1_index is None:
        raise RuntimeError("Missing <h1>")

    hr_index = None
    for i in range(h1_index + 1, len(children)):
        if children[i].tag == f"{{{XHTML_NS}}}hr":
            hr_index = i
            break
    if hr_index is None:
        raise RuntimeError("Missing <hr/> after metadata")

    return children, h1_index, hr_index


def _has_occurrence(children: list[etree._Element], h1_index: int, hr_index: int) -> bool:
    for c in children[h1_index + 1 : hr_index]:
        if c.tag != f"{{{XHTML_NS}}}p":
            continue
        txt = _collapse_ws("".join(c.itertext()))
        if txt.lower().startswith("occurrence:"):
            return True
    return False


def _infer_occurrence(children: list[etree._Element], h1_index: int, hr_index: int) -> str:
    # Look at metadata block text only.
    meta_texts = [
        _collapse_ws("".join(c.itertext()))
        for c in children[h1_index + 1 : hr_index]
        if c.tag == f"{{{XHTML_NS}}}p"
    ]

    all_meta = "\n".join(meta_texts)

    # Explicit category flags
    if any(t.strip().lower() == "fanfic" for t in meta_texts):
        return "Fanfic (non-canon)"

    # WN post-ending stories
    if "web novel" in all_meta.lower() and "after its conclusion" in all_meta.lower():
        return "Web Novel (post-ending)"

    # Blu-ray shorts (and related) in this repo include a season 2 / volume 3-4-ish note.
    # Standardize to the repo’s canonical Occurrence vocabulary.
    if "season 2" in all_meta.lower():
        m = _VOL_RANGE_RE.search(all_meta)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            lo, hi = (a, b) if a <= b else (b, a)
            return f"Around Volumes {lo}–{hi}"
        return "Around Volumes 3–4"

    # Natsume blog stories in this repo state around volume 4 in their note.
    if any(t.startswith("Natsume’s blog") or t.startswith("Natsume's blog") for t in meta_texts):
        return "Around Volume 4"

    # Try to parse explicit volume hints in notes
    for t in meta_texts:
        m = _VOL_RANGE_RE.search(t)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            lo, hi = (a, b) if a <= b else (b, a)
            return f"Around Volumes {lo}–{hi}"

    for t in meta_texts:
        m = _VOL_SINGLE_RE.search(t)
        if m:
            return f"Around Volume {int(m.group(1))}"

    # Fallback
    return "Timeline unspecified"


def _insert_occurrence(tree: etree._ElementTree, occurrence: str) -> bool:
    root = tree.getroot()
    body = root.find('.//xhtml:body', namespaces=NS)
    if body is None:
        raise RuntimeError("Missing <body>")

    children, h1_index, hr_index = _metadata_children(body)

    if _has_occurrence(children, h1_index, hr_index):
        return False

    # Find insertion point
    insert_after = None
    for i in range(h1_index + 1, hr_index):
        c = children[i]
        if c.tag != f"{{{XHTML_NS}}}p":
            continue
        txt = _collapse_ws("".join(c.itertext()))
        if txt.startswith("Editors:"):
            insert_after = c

    if insert_after is None:
        for i in range(h1_index + 1, hr_index):
            c = children[i]
            if c.tag != f"{{{XHTML_NS}}}p":
                continue
            txt = _collapse_ws("".join(c.itertext()))
            if txt.startswith("Translator:"):
                insert_after = c
                break

    new_p = etree.Element(f"{{{XHTML_NS}}}p")
    new_p.text = f"Occurrence: {occurrence}"

    if insert_after is None:
        # Insert just before hr
        body.insert(body.index(children[hr_index]), new_p)
    else:
        body.insert(body.index(insert_after) + 1, new_p)

    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub-dir", default="English-Localized/EPUB")
    args = ap.parse_args()

    epub_dir = Path(args.epub_dir)
    if not epub_dir.exists() or not epub_dir.is_dir():
        print(f"epub-dir not found: {epub_dir}", file=sys.stderr)
        return 2

    changed: list[Change] = []

    for path in sorted(epub_dir.glob("*.xhtml")):
        if path.name in EXCLUDE:
            continue

        tree = _read_xml(path)
        root = tree.getroot()
        body = root.find('.//xhtml:body', namespaces=NS)
        if body is None:
            continue

        children, h1_index, hr_index = _metadata_children(body)
        if _has_occurrence(children, h1_index, hr_index):
            continue

        occurrence = _infer_occurrence(children, h1_index, hr_index)
        if _insert_occurrence(tree, occurrence):
            path.write_bytes(etree.tostring(tree, encoding="utf-8", xml_declaration=True, pretty_print=True))
            changed.append(Change(path=path, occurrence=occurrence))

    print(f"UPDATED {len(changed)}")
    for c in changed:
        print(f"{c.path.name}\t{c.occurrence}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
