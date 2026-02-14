#!/usr/bin/env python3
"""Scan English-Localized story XHTML files for structure + punctuation issues.

Focused on the requirements in:
- English-Localized/LOCALIZATION_STYLE_GUIDE.md (Unicode punctuation preference)
- English-Localized/XHTML_STRUCTURE_GUIDE.md (canonical skeleton)

This script is read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


EXCLUDE = {
    "nav.xhtml",
    "cover.xhtml",
    "copyright.xhtml",
    "translators.xhtml",
}

XHTML_NS = "http://www.w3.org/1999/xhtml"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


@dataclass(frozen=True)
class FileReport:
    path: Path
    parse_error: str | None
    structure_issues: tuple[str, ...]
    punct_counts: dict[str, int]


def _first_line(path: Path) -> str:
    with path.open("rb") as f:
        line = f.readline()
    try:
        return line.decode("utf-8").rstrip("\n").rstrip("\r")
    except UnicodeDecodeError:
        return ""


def _count_text_punct(tree: etree._ElementTree) -> dict[str, int]:
    # Count only in text nodes (not tag/attribute text).
    text = "".join(tree.xpath("//text()"))

    patterns: dict[str, re.Pattern[str]] = {
        "straight_double": re.compile(r'"'),
        "straight_single": re.compile(r"'"),
        "quot_entity": re.compile(r"&quot;"),
        "apos_entity": re.compile(r"&apos;"),
        "three_dots": re.compile(r"\.\.\."),
        "double_hyphen": re.compile(r"--"),
    }

    return {k: len(p.findall(text)) for k, p in patterns.items()}


def _check_structure(path: Path, tree: etree._ElementTree) -> tuple[str, ...]:
    issues: list[str] = []

    if _first_line(path) != "<?xml version='1.0' encoding='utf-8'?>":
        issues.append("xml-prolog")

    root = tree.getroot()
    if root.tag != f"{{{XHTML_NS}}}html":
        issues.append("root-not-xhtml-html")
        return tuple(issues)

    if root.get("lang") != "en" or root.get(XML_LANG) != "en":
        issues.append("lang-attrs")

    # namespace declarations / epub:prefix are not reliably introspectable after parse;
    # we check for the attribute by name.
    if root.get("{http://www.idpf.org/2007/ops}prefix") is None and root.get("epub:prefix") is None:
        issues.append("missing-epub-prefix")

    head = root.find(f"{{{XHTML_NS}}}head")
    body = root.find(f"{{{XHTML_NS}}}body")

    if head is None:
        issues.append("missing-head")
    else:
        titles = head.findall(f"{{{XHTML_NS}}}title")
        if len(titles) != 1:
            issues.append(f"title-count-{len(titles)}")

    if body is None:
        issues.append("missing-body")
        return tuple(issues)

    h1s = body.findall(f"{{{XHTML_NS}}}h1")
    if len(h1s) != 1:
        issues.append(f"h1-count-{len(h1s)}")

    # Metadata block: <p> lines after <h1> until first <hr/>
    children = [c for c in body if isinstance(c.tag, str)]
    h1_index = next((i for i, c in enumerate(children) if c.tag == f"{{{XHTML_NS}}}h1"), None)

    if h1_index is not None:
        meta_ps: list[str] = []
        found_hr = False
        for c in children[h1_index + 1 :]:
            if c.tag == f"{{{XHTML_NS}}}hr":
                found_hr = True
                break
            if c.tag == f"{{{XHTML_NS}}}p":
                meta_ps.append("".join(c.itertext()).strip())
                continue
            if "".join(c.itertext()).strip():
                issues.append("non-p-in-metadata-block")
            break

        if not meta_ps:
            issues.append("missing-metadata-block")
        else:
            if not any(t.startswith("Translator:") for t in meta_ps):
                issues.append("missing-translator")
            # Structure guide allows additional metadata <p> lines (rare) as long as they
            # stay grouped under the <h1>. We only enforce that when the canonical labels
            # appear, they keep their exact form.

        if not found_hr:
            issues.append("missing-hr-after-metadata")

    hrs = body.findall(f".//{{{XHTML_NS}}}hr")
    if len(hrs) < 2:
        issues.append(f"hr-count-{len(hrs)}")
    else:
        if children and children[-1].tag != f"{{{XHTML_NS}}}hr":
            issues.append("missing-final-hr")

    # Title/h1 match (normalized whitespace)
    if head is not None and body is not None:
        title_el = head.find(f"{{{XHTML_NS}}}title")
        h1_el = body.find(f"{{{XHTML_NS}}}h1")
        if title_el is not None and h1_el is not None:
            title = " ".join((title_el.text or "").split())
            h1 = " ".join("".join(h1_el.itertext()).split())
            if title and h1 and title != h1:
                issues.append("title-h1-mismatch")

    return tuple(issues)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--epub-dir",
        default="English-Localized/EPUB",
        help="Directory containing the story .xhtml files (default: English-Localized/EPUB)",
    )
    args = ap.parse_args()

    epub_dir = Path(args.epub_dir)
    if not epub_dir.exists() or not epub_dir.is_dir():
        print(f"epub-dir not found or not a directory: {epub_dir}")
        return 2

    files = sorted(p for p in epub_dir.glob("*.xhtml") if p.name not in EXCLUDE)
    if not files:
        print("No XHTML files found.")
        return 1

    reports: list[FileReport] = []

    parser = etree.XMLParser(resolve_entities=False, recover=False, remove_comments=False)

    for i, path in enumerate(files, start=1):
        if i % 10 == 0:
            print(f"... scanned {i}/{len(files)}", file=sys.stderr)

        try:
            tree = etree.parse(str(path), parser)
        except Exception as e:
            reports.append(
                FileReport(path=path, parse_error=str(e), structure_issues=("xml-parse-error",), punct_counts={})
            )
            continue

        struct = _check_structure(path, tree)
        punct = _count_text_punct(tree)

        reports.append(FileReport(path=path, parse_error=None, structure_issues=struct, punct_counts=punct))

    # Summary
    parse_errors = [r for r in reports if r.parse_error]
    struct_bad = [r for r in reports if r.structure_issues]
    punct_bad = [r for r in reports if any(v > 0 for v in r.punct_counts.values())]

    total_counts: dict[str, int] = {}
    for r in reports:
        for k, v in r.punct_counts.items():
            total_counts[k] = total_counts.get(k, 0) + v

    print("SUMMARY")
    print("files", len(reports))
    print("parse_errors", len(parse_errors))
    print("structure_issue_files", len(struct_bad))
    print("punct_issue_files", len(punct_bad))
    for k in sorted(total_counts):
        print(k, total_counts[k])

    # Top punctuation offenders
    punct_bad_sorted = sorted(
        punct_bad,
        key=lambda r: (
            r.punct_counts.get("straight_double", 0)
            + r.punct_counts.get("quot_entity", 0),
            r.punct_counts.get("straight_single", 0)
            + r.punct_counts.get("apos_entity", 0),
            r.punct_counts.get("three_dots", 0),
            r.punct_counts.get("double_hyphen", 0),
        ),
        reverse=True,
    )

    print("\nTOP_PUNCT (15)")
    for r in punct_bad_sorted[:15]:
        print(r.path.as_posix(), r.punct_counts)

    print("\nSTRUCTURE_ISSUES (first 40)")
    for r in struct_bad[:40]:
        print(r.path.as_posix(), list(r.structure_issues))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
