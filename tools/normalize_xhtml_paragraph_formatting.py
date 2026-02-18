#!/usr/bin/env python3
"""Normalize paragraph formatting in English-Localized XHTML files.

This repo primarily stores each <p> on its own line, with blank lines between
metadata paragraphs. Some scripts that roundtrip through XML serializers can
produce:
- Adjacent paragraphs on one line: </p><p>
- Self-closing paragraph tags: <p/>

These are valid XML, but they make diffs noisy and inconsistent with the repo's
style. This script performs conservative, text-only normalization:
- Replace <p/> (and <p />) with <p></p>
- Replace </p><p with </p>\n\n  <p (splitting adjacent paragraphs)

It does not attempt to reindent the whole file or change any content.

Usage:
  python tools/normalize_xhtml_paragraph_formatting.py --epub-dir English-Localized/EPUB

Exit codes:
  0 success
  2 invalid arguments
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


EXCLUDE = {
    "content.opf",
    "mimetype",
    "toc.ncx",
}


def _normalize_text(text: str) -> str:
    # Normalize common serializer artifacts.
    text = text.replace("<p />", "<p></p>")
    text = text.replace("<p/>", "<p></p>")

    # Ensure adjacent paragraphs are separated.
    # Only touches explicit boundary token sequence.
    text = text.replace("</p><p", "</p>\n\n  <p")

    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub-dir", default="English-Localized/EPUB")
    ap.add_argument("--check", action="store_true", help="Only report which files would change")
    args = ap.parse_args()

    epub_dir = Path(args.epub_dir)
    if not epub_dir.exists() or not epub_dir.is_dir():
        print(f"epub-dir not found: {epub_dir}", file=sys.stderr)
        return 2

    changed: list[Path] = []

    for path in sorted(epub_dir.glob("*.xhtml")):
        if path.name in EXCLUDE:
            continue

        original = path.read_text(encoding="utf-8")
        updated = _normalize_text(original)

        if updated == original:
            continue

        changed.append(path)

        if not args.check:
            path.write_text(updated, encoding="utf-8")

    print(f"changed_files {len(changed)}")
    for p in changed:
        print(p.as_posix())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
