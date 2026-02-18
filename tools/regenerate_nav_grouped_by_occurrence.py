#!/usr/bin/env python3
"""Regenerate English-Localized/EPUB/nav.xhtml grouped by story Occurrence.

This script keeps the EPUB3 TOC valid by using nested <ol> sections in nav.xhtml.
It does NOT change the spine order in content.opf.

Grouping rules (intentionally simple):
- Non-story entries (copyright, translator credits) stay at the top.
- Stories are grouped by the exact Occurrence line value from each story file:
    <p>Occurrence: ...</p>
- Group ordering is derived from a best-effort sort on the Occurrence string:
    * If the occurrence mentions a volume number, groups with the same prefix are
        sorted numerically by that volume.
    * Otherwise, groups are ordered by first appearance in the spine.
- Within a group, story order follows the spine order.

Usage:
  python tools/regenerate_nav_grouped_by_occurrence.py
  python tools/regenerate_nav_grouped_by_occurrence.py --epub-dir English-Localized/EPUB

Exit codes:
  0 success
  2 invalid args / missing files
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


XHTML_NS = "http://www.w3.org/1999/xhtml"
OPF_NS = "http://www.idpf.org/2007/opf"
EPUB_NS = "http://www.idpf.org/2007/ops"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

NS = {
    "opf": OPF_NS,
    "xhtml": XHTML_NS,
    "epub": EPUB_NS,
}


EXCLUDE_FROM_GROUPING = {
    "nav.xhtml",
    "cover.xhtml",
    "toc.ncx",
}

PINNED_TOP = {
    "copyright.xhtml",
    "translators.xhtml",
}


@dataclass(frozen=True)
class TocItem:
    href: str
    label: str
    occurrence: str | None


_VOL_RE = re.compile(r"\b(?:vol(?:ume)?\.?|volume)\s*(\d+)\b", re.IGNORECASE)


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def _read_xml(path: Path) -> etree._ElementTree:
    parser = etree.XMLParser(resolve_entities=False, recover=False, remove_blank_text=False)
    return etree.parse(str(path), parser)


def _extract_spine_hrefs(opf_path: Path) -> list[str]:
    tree = _read_xml(opf_path)

    # idref order
    idrefs = [
        el.get("idref")
        for el in tree.findall(".//opf:spine/opf:itemref", namespaces=NS)
        if el.get("idref")
    ]

    manifest = {
        el.get("id"): el.get("href")
        for el in tree.findall(".//opf:manifest/opf:item", namespaces=NS)
        if el.get("id") and el.get("href")
    }

    hrefs: list[str] = []
    for idref in idrefs:
        href = manifest.get(idref)
        if not href:
            continue
        hrefs.append(href)

    return hrefs


def _extract_nav_labels(nav_tree: etree._ElementTree) -> dict[str, str]:
    root = nav_tree.getroot()

    # Find the TOC nav/ol
    nav_el = root.find(".//xhtml:nav[@epub:type='toc']", namespaces=NS)
    if nav_el is None:
        nav_el = root.find(".//xhtml:nav", namespaces=NS)
    if nav_el is None:
        return {}

    labels: dict[str, str] = {}
    for a in nav_el.findall(".//xhtml:a", namespaces=NS):
        href = a.get("href")
        if not href:
            continue
        labels[href] = _collapse_ws("".join(a.itertext()))

    return labels


def _extract_occurrence(story_path: Path) -> str | None:
    try:
        tree = _read_xml(story_path)
    except Exception:
        return None

    root = tree.getroot()

    body = root.find(".//xhtml:body", namespaces=NS)
    if body is None:
        return None

    # Metadata block is a series of <p> under <h1> until first <hr/>.
    children = [c for c in body if isinstance(c.tag, str)]
    h1_index = next((i for i, c in enumerate(children) if c.tag == f"{{{XHTML_NS}}}h1"), None)
    if h1_index is None:
        return None

    for c in children[h1_index + 1 :]:
        if c.tag == f"{{{XHTML_NS}}}hr":
            break
        if c.tag != f"{{{XHTML_NS}}}p":
            continue
        text = _collapse_ws("".join(c.itertext()))
        if text.lower().startswith("occurrence:"):
            value = _collapse_ws(text.split(":", 1)[1])
            return value or None

    return None


def _group_sort_key(label: str) -> tuple:
    """Sort occurrence group headings into a stable, reader-friendly order.

    Desired top-level order (per user):
      1) Volumes
      2) Web Novel (post-ending)
      3) Explosions
      4) Continued Explosions
      5) Dust Spinoffs
      6) Everyday life
      7) Timeline unspecified
      8) Fanfic

    Within each bucket we sort numerically when a volume number is present.
    """

    raw = label or ""
    lower = raw.lower()

    def first_int_or_none(s: str) -> int | None:
        m = _VOL_RE.search(s)
        return int(m.group(1)) if m else None

    # Bucket assignment
    if raw == "(Missing Occurrence)":
        bucket = 7
        vol = None
    elif raw == "Fanfic (non-canon)":
        bucket = 8
        vol = None
    elif raw == "Timeline unspecified":
        bucket = 7
        vol = None
    elif raw == "Web Novel (post-ending)":
        bucket = 2
        vol = None
    elif "continued explosions" in lower:
        bucket = 4
        vol = first_int_or_none(raw)
    elif "dust spinoff" in lower:
        bucket = 5
        vol = first_int_or_none(raw)
    elif "everyday life" in lower or "nichijou" in lower:
        bucket = 6
        vol = first_int_or_none(raw)
    elif "explosions" in lower:
        bucket = 3
        vol = first_int_or_none(raw)
    else:
        # Default to mainline volumes bucket.
        bucket = 1
        vol = first_int_or_none(raw)

    # Secondary sort key
    # Keep a series prefix so "Around Volume" sorts independently of other forms.
    m = _VOL_RE.search(raw)
    prefix = _collapse_ws(raw[: m.start()]).lower() if m else _collapse_ws(raw).lower()
    vol_key = vol if vol is not None else 10**9

    return (bucket, prefix, vol_key, lower)


def _indent(elem: etree._Element, level: int = 0) -> None:
    # Minimal pretty indentation to match repo style (2 spaces).
    # Ensure siblings are separated (avoid "</li><li>" on one line).
    i = "\n" + level * "  "

    if len(elem):
        if not (elem.text and elem.text.strip()):
            elem.text = i + "  "

        for child in elem:
            _indent(child, level + 1)
            if not (child.tail and child.tail.strip()):
                child.tail = i + "  "

        if not (elem[-1].tail and elem[-1].tail.strip()):
            elem[-1].tail = i
    else:
        if level and not (elem.tail and elem.tail.strip()):
            elem.tail = i


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub-dir", default="English-Localized/EPUB")
    args = ap.parse_args()

    epub_dir = Path(args.epub_dir)
    if not epub_dir.exists() or not epub_dir.is_dir():
        print(f"epub-dir not found: {epub_dir}", file=sys.stderr)
        return 2

    opf_path = epub_dir / "content.opf"
    nav_path = epub_dir / "nav.xhtml"

    if not opf_path.exists() or not nav_path.exists():
        print("Missing content.opf or nav.xhtml", file=sys.stderr)
        return 2

    spine_hrefs = _extract_spine_hrefs(opf_path)

    nav_tree = _read_xml(nav_path)
    labels_by_href = _extract_nav_labels(nav_tree)

    # Build ordered items (spine order), skipping non-XHTML and excluded.
    items: list[TocItem] = []
    missing_occurrence: list[str] = []

    for href in spine_hrefs:
        if href in EXCLUDE_FROM_GROUPING:
            continue
        if not href.endswith(".xhtml"):
            continue

        label = labels_by_href.get(href) or href

        occurrence: str | None = None
        if href not in PINNED_TOP:
            occurrence = _extract_occurrence(epub_dir / href)
            if occurrence is None:
                missing_occurrence.append(href)

        items.append(TocItem(href=href, label=label, occurrence=occurrence))

    # Grouping
    pinned = [it for it in items if it.href in PINNED_TOP]
    stories = [it for it in items if it.href not in PINNED_TOP]

    groups_in_spine_order: list[str] = []
    groups: dict[str, list[TocItem]] = {}

    for it in stories:
        group = it.occurrence or "(Missing Occurrence)"
        if group not in groups:
            groups[group] = []
            groups_in_spine_order.append(group)
        groups[group].append(it)

    group_labels = sorted(groups_in_spine_order, key=_group_sort_key)

    # Rebuild nav.xhtml <ol>
    root = nav_tree.getroot()
    nav_el = root.find(".//xhtml:nav[@epub:type='toc']", namespaces=NS)
    if nav_el is None:
        nav_el = root.find(".//xhtml:nav", namespaces=NS)
    if nav_el is None:
        raise RuntimeError("nav.xhtml missing <nav>")

    ol = nav_el.find(".//xhtml:ol", namespaces=NS)
    if ol is None:
        raise RuntimeError("nav.xhtml missing <ol>")

    # Clear existing top-level list.
    for child in list(ol):
        ol.remove(child)

    def add_link_li(parent_ol: etree._Element, href: str, label: str) -> None:
        li = etree.SubElement(parent_ol, f"{{{XHTML_NS}}}li")
        a = etree.SubElement(li, f"{{{XHTML_NS}}}a")
        a.set("href", href)
        a.text = label

    # Pinned top entries (copyright, translators) in their original spine order.
    for it in pinned:
        add_link_li(ol, it.href, it.label)

    # Grouped stories
    for group_label in group_labels:
        li = etree.SubElement(ol, f"{{{XHTML_NS}}}li")
        span = etree.SubElement(li, f"{{{XHTML_NS}}}span")
        span.text = group_label
        sub_ol = etree.SubElement(li, f"{{{XHTML_NS}}}ol")

        for it in groups[group_label]:
            add_link_li(sub_ol, it.href, it.label)

    _indent(root)

    nav_path.write_bytes(
        etree.tostring(nav_tree, encoding="utf-8", xml_declaration=True, pretty_print=False)
    )

    if missing_occurrence:
        print("MISSING_OCCURRENCE", len(missing_occurrence))
        for href in missing_occurrence:
            print(href)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
