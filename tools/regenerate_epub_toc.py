#!/usr/bin/env python3
"""Regenerate EPUB navigation files (EPUB 3 package + nav + NCX).

Targets:
- English-Localized/EPUB/content.opf
- English-Localized/EPUB/nav.xhtml
- English-Localized/EPUB/toc.ncx

Design goals:
- Preserve existing <metadata> from content.opf (only updates dcterms:modified).
- Preserve existing spine order from content.opf.
- Rebuild manifest from actual files on disk.
- Rebuild nav.xhtml and toc.ncx labels from each XHTML's <h1> (fallback: <title>, fallback: filename).

This is intentionally conservative: it does not rename files or reorder spine.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from lxml import etree


XHTML_NS = "http://www.w3.org/1999/xhtml"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
EPUB_NS = "http://www.idpf.org/2007/ops"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NS = {
    "opf": OPF_NS,
    "dc": DC_NS,
    "xhtml": XHTML_NS,
    "epub": EPUB_NS,
    "ncx": NCX_NS,
}


@dataclass(frozen=True)
class TocEntry:
    idref: str
    href: str
    title: str


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_xml(path: Path) -> etree._ElementTree:
    parser = etree.XMLParser(resolve_entities=False, recover=False, remove_blank_text=False)
    return etree.parse(str(path), parser)


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def _extract_book_title(opf_tree: etree._ElementTree) -> str:
    title_el = opf_tree.find(".//dc:title", namespaces=NS)
    return _collapse_ws(title_el.text if title_el is not None else "") or "Table of Contents"


def _extract_uid(opf_tree: etree._ElementTree) -> str:
    # Prefer dc:identifier with id="id" (matches unique-identifier="id" in package).
    uid_el = opf_tree.find(".//dc:identifier[@id='id']", namespaces=NS)
    if uid_el is not None and _collapse_ws(uid_el.text):
        return _collapse_ws(uid_el.text)

    # Else use package unique-identifier attribute to look up.
    pkg = opf_tree.getroot()
    uid_id = pkg.get("unique-identifier")
    if uid_id:
        el = opf_tree.find(f".//dc:identifier[@id='{uid_id}']", namespaces=NS)
        if el is not None and _collapse_ws(el.text):
            return _collapse_ws(el.text)

    # Else fall back to first dc:identifier.
    first = opf_tree.find(".//dc:identifier", namespaces=NS)
    return _collapse_ws(first.text if first is not None else "konosuba-short-stories") or "konosuba-short-stories"


def _extract_spine_idrefs(opf_tree: etree._ElementTree) -> list[str]:
    return [
        el.get("idref")
        for el in opf_tree.findall(".//opf:spine/opf:itemref", namespaces=NS)
        if el.get("idref")
    ]


def _media_type_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in {".xhtml", ".html"}:
        return "application/xhtml+xml"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".svg":
        return "image/svg+xml"
    if ext == ".ncx":
        return "application/x-dtbncx+xml"
    if ext == ".css":
        return "text/css"
    return None


def _manifest_id_for(path: Path) -> str:
    # Keep existing conventions from the repo.
    name = path.name
    if name == "nav.xhtml":
        return "nav"
    if name == "toc.ncx":
        return "ncx"
    if name == "cover.xhtml":
        return "cover"
    if name == "copyright.xhtml":
        return "copyright"
    if name == "translators.xhtml":
        return "translators"
    if name == "cover.jpeg":
        return "cover-img"

    stem = path.stem
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".svg"}:
        return f"{stem}-img"

    return stem


def _extract_xhtml_title(xhtml_path: Path) -> str:
    parser = etree.XMLParser(resolve_entities=False, recover=False, remove_blank_text=False)
    tree = etree.parse(str(xhtml_path), parser)
    root = tree.getroot()

    # Prefer the first <h1> anywhere in the body.
    h1 = root.find(".//xhtml:body//xhtml:h1", namespaces=NS)
    if h1 is not None:
        text = _collapse_ws("".join(h1.itertext()))
        if text:
            return text

    # Fallback to <title>
    title_el = root.find(".//xhtml:head/xhtml:title", namespaces=NS)
    if title_el is not None:
        text = _collapse_ws("".join(title_el.itertext()))
        if text:
            return text

    return xhtml_path.stem


def _iter_epub_files(epub_dir: Path) -> list[Path]:
    # Only top-level files in this repo layout.
    return sorted(p for p in epub_dir.iterdir() if p.is_file())


def _build_manifest_items(epub_dir: Path) -> list[tuple[str, str, str, list[str]]]:
    # Returns: (id, href, media_type, properties)
    items: list[tuple[str, str, str, list[str]]] = []

    for p in _iter_epub_files(epub_dir):
        mt = _media_type_for(p)
        if not mt:
            continue

        item_id = _manifest_id_for(p)
        href = p.name
        props: list[str] = []

        if p.name == "nav.xhtml":
            props.append("nav")
        if p.name == "cover.jpeg":
            props.append("cover-image")

        items.append((item_id, href, mt, props))

    # Ensure required items exist even if missing from dir.
    return items


def _write_content_opf(epub_dir: Path, opf_tree: etree._ElementTree, spine_idrefs: list[str]) -> None:
    pkg = etree.Element(f"{{{OPF_NS}}}package", nsmap={None: OPF_NS})

    # Copy over package attrs that matter.
    old_pkg = opf_tree.getroot()
    for k, v in old_pkg.attrib.items():
        pkg.set(k, v)

    # Copy metadata element (deep copy).
    old_metadata = opf_tree.find(".//opf:metadata", namespaces=NS)
    if old_metadata is None:
        raise RuntimeError("content.opf missing <metadata>")

    metadata = etree.fromstring(etree.tostring(old_metadata))

    # Update dcterms:modified
    modified_xpath = ".//opf:meta[@property='dcterms:modified']"
    modified = metadata.find(modified_xpath, namespaces=NS)
    if modified is None:
        modified = etree.SubElement(metadata, f"{{{OPF_NS}}}meta")
        modified.set("property", "dcterms:modified")
    modified.text = _utc_timestamp()

    pkg.append(metadata)

    manifest = etree.SubElement(pkg, f"{{{OPF_NS}}}manifest")
    for item_id, href, media_type, props in _build_manifest_items(epub_dir):
        item = etree.SubElement(manifest, f"{{{OPF_NS}}}item")
        item.set("id", item_id)
        item.set("href", href)
        item.set("media-type", media_type)
        if props:
            item.set("properties", " ".join(props))

    spine = etree.SubElement(pkg, f"{{{OPF_NS}}}spine")
    old_spine = opf_tree.find(".//opf:spine", namespaces=NS)
    if old_spine is not None:
        for k, v in old_spine.attrib.items():
            spine.set(k, v)

    # Re-add itemrefs in existing order, skipping any missing from manifest.
    manifest_ids = {el.get("id") for el in manifest.findall(".//opf:item", namespaces=NS)}
    for idref in spine_idrefs:
        if idref not in manifest_ids:
            continue
        itemref = etree.SubElement(spine, f"{{{OPF_NS}}}itemref")
        itemref.set("idref", idref)

    out_path = epub_dir / "content.opf"
    out_path.write_bytes(
        etree.tostring(
            pkg,
            encoding="utf-8",
            xml_declaration=False,  # existing file has no xml prolog
            pretty_print=True,
        )
    )


def _build_toc_entries(epub_dir: Path, opf_tree: etree._ElementTree, spine_idrefs: list[str]) -> list[TocEntry]:
    # Map id->href from existing OPF manifest (filenames unchanged).
    manifest_items = {
        el.get("id"): el.get("href")
        for el in opf_tree.findall(".//opf:manifest/opf:item", namespaces=NS)
        if el.get("id") and el.get("href")
    }

    # Prefer: nav excludes itself and cover.
    exclude = {"nav", "cover"}

    entries: list[TocEntry] = []
    for idref in spine_idrefs:
        if idref in exclude:
            continue
        href = manifest_items.get(idref)
        if not href:
            # fallback based on idref
            if (epub_dir / f"{idref}.xhtml").exists():
                href = f"{idref}.xhtml"
            else:
                continue

        title = _extract_xhtml_title(epub_dir / href) if href.endswith(".xhtml") else idref
        entries.append(TocEntry(idref=idref, href=href, title=title))

    return entries


def _write_nav_xhtml(epub_dir: Path, book_title: str, entries: list[TocEntry]) -> None:
    nsmap = {None: XHTML_NS, "epub": EPUB_NS}
    html = etree.Element(f"{{{XHTML_NS}}}html", nsmap=nsmap)
    html.set("lang", "en")
    html.set(f"{{{XML_NS}}}lang", "en")

    head = etree.SubElement(html, f"{{{XHTML_NS}}}head")
    title = etree.SubElement(head, f"{{{XHTML_NS}}}title")
    title.text = book_title

    body = etree.SubElement(html, f"{{{XHTML_NS}}}body")

    nav = etree.SubElement(body, f"{{{XHTML_NS}}}nav")
    nav.set(f"{{{EPUB_NS}}}type", "toc")
    nav.set("id", "toc")
    nav.set("role", "doc-toc")

    h2 = etree.SubElement(nav, f"{{{XHTML_NS}}}h2")
    h2.text = book_title

    ol = etree.SubElement(nav, f"{{{XHTML_NS}}}ol")

    for e in entries:
        li = etree.SubElement(ol, f"{{{XHTML_NS}}}li")
        a = etree.SubElement(li, f"{{{XHTML_NS}}}a")
        a.set("href", e.href)
        a.text = e.title

    out_path = epub_dir / "nav.xhtml"
    out_path.write_bytes(
        b"<?xml version='1.0' encoding='utf-8'?>\n"
        + etree.tostring(html, encoding="utf-8", pretty_print=True, xml_declaration=False)
    )


def _write_toc_ncx(epub_dir: Path, uid: str, book_title: str, entries: list[TocEntry]) -> None:
    ncx = etree.Element(f"{{{NCX_NS}}}ncx", nsmap={None: NCX_NS})
    ncx.set("version", "2005-1")

    head = etree.SubElement(ncx, f"{{{NCX_NS}}}head")
    for name, content in (
        ("dtb:uid", uid),
        ("dtb:depth", "1"),
        ("dtb:totalPageCount", "0"),
        ("dtb:maxPageNumber", "0"),
    ):
        meta = etree.SubElement(head, f"{{{NCX_NS}}}meta")
        meta.set("name", name)
        meta.set("content", content)

    doc_title = etree.SubElement(ncx, f"{{{NCX_NS}}}docTitle")
    text_el = etree.SubElement(doc_title, f"{{{NCX_NS}}}text")
    text_el.text = book_title

    nav_map = etree.SubElement(ncx, f"{{{NCX_NS}}}navMap")

    play_order = 1
    for e in entries:
        np = etree.SubElement(nav_map, f"{{{NCX_NS}}}navPoint")
        np.set("id", e.idref)
        np.set("playOrder", str(play_order))
        play_order += 1

        nav_label = etree.SubElement(np, f"{{{NCX_NS}}}navLabel")
        lbl_text = etree.SubElement(nav_label, f"{{{NCX_NS}}}text")
        lbl_text.text = e.title

        content = etree.SubElement(np, f"{{{NCX_NS}}}content")
        content.set("src", e.href)

    out_path = epub_dir / "toc.ncx"
    out_path.write_bytes(
        b"<?xml version='1.0' encoding='utf-8'?>\n" + etree.tostring(ncx, encoding="utf-8", pretty_print=True)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub-dir", default="English-Localized/EPUB")
    args = ap.parse_args()

    epub_dir = Path(args.epub_dir)
    opf_path = epub_dir / "content.opf"
    if not opf_path.exists():
        raise SystemExit(f"Missing {opf_path}")

    opf_tree = _read_xml(opf_path)
    spine_idrefs = _extract_spine_idrefs(opf_tree)

    book_title = _extract_book_title(opf_tree)
    uid = _extract_uid(opf_tree)

    # Build TOC entries from original spine order (excluding nav/cover).
    entries = _build_toc_entries(epub_dir, opf_tree, spine_idrefs)

    # Write files
    _write_content_opf(epub_dir, opf_tree, spine_idrefs)
    _write_nav_xhtml(epub_dir, book_title, entries)
    _write_toc_ncx(epub_dir, uid, book_title, entries)

    print(f"wrote content.opf, nav.xhtml, toc.ncx in {epub_dir}")
    print(f"toc_entries {len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
