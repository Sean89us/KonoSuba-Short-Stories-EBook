#!/usr/bin/env python3
"""Pull a short story from the web and save as EPUB-friendly XHTML.

Primary use-case: WordPress translation blogs (e.g., cgtranslations.me) where the
story text lives under a content container like <div class="entry-content">.

This script intentionally focuses on producing a clean, well-formed story XHTML
file that matches this repo's structure guide:
  English-Localized/XHTML_STRUCTURE_GUIDE.md

Usage:
  python tools/pull_story_from_web.py URL

Examples:
  python tools/pull_story_from_web.py \
	https://cgtranslations.me/2018/04/09/volume-2-short-story-megumin-the-dragon-slayer/

  python tools/pull_story_from_web.py URL --translator Cannongerbil --occurrence "Volume 2"

Dependencies:
  - requests
  - beautifulsoup4
  - (optional) lxml (BeautifulSoup parser)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
import mimetypes


try:
	import requests
except ModuleNotFoundError as e:  # pragma: no cover
	raise SystemExit(
		"Missing dependency 'requests'. Install with: pip install requests"
	) from e

try:
	from bs4 import BeautifulSoup
	from bs4.element import Tag
except ModuleNotFoundError as e:  # pragma: no cover
	raise SystemExit(
		"Missing dependency 'beautifulsoup4'. Install with: pip install beautifulsoup4"
	) from e


HEADERS = {
	"User-Agent": "Mozilla/5.0 (KonoSuba-Short-Stories-EBook pull_story_from_web.py; personal use)",
}


_METADATA_LINE_RE = re.compile(
	r"^\s*(translator|tl|translated\s+by|editors?|editor|editing|occurrence)\s*:\s*(.*?)\s*$",
	flags=re.IGNORECASE,
)


def _repo_root() -> Path:
	# tools/ -> repo root
	return Path(__file__).resolve().parents[1]


def _slugify_story_filename(title: str) -> str:
	"""Convert a title into this repo's story filename convention.

	Rules (see XHTML_STRUCTURE_GUIDE.md):
	- lowercase only
	- no spaces/dashes/underscores
	- run-together words
	"""
	s = title.strip().lower()
	# Replace common dash characters with spaces, then remove non-alphanumerics.
	s = s.replace("—", " ").replace("–", " ").replace("-", " ")
	words = re.findall(r"[a-z0-9]+", s)
	base = "".join(words) or "story"
	return f"{base}.xhtml"


def _pick_bs4_parser() -> str:
	# Prefer lxml when available, but fall back gracefully.
	try:
		import lxml  # noqa: F401

		return "lxml"
	except ModuleNotFoundError:
		return "html.parser"


def _fetch_html(url: str) -> str:
	r = requests.get(url, headers=HEADERS, timeout=30)
	r.raise_for_status()
	# requests will decode based on headers; ensure we return text.
	return r.text


def _extract_title(soup: BeautifulSoup) -> str | None:
	# WordPress often uses these.
	for selector in (
		"h1.entry-title",
		"header h1",
		"article h1",
		"h1",
	):
		h = soup.select_one(selector)
		if h and h.get_text(strip=True):
			return h.get_text(" ", strip=True)
	if soup.title and soup.title.get_text(strip=True):
		return soup.title.get_text(" ", strip=True)
	return None


_TITLE_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
	re.compile(r"^\s*volume\s*\d+\s*short\s*stor(?:y|ies)\s*[:\-–—]\s*(.+?)\s*$", re.IGNORECASE),
	re.compile(r"^\s*vol\.?\s*\d+\s*short\s*stor(?:y|ies)\s*[:\-–—]\s*(.+?)\s*$", re.IGNORECASE),
)


def _cleanup_title(title: str) -> str:
	t = " ".join(title.split()).strip()
	for pat in _TITLE_PREFIX_PATTERNS:
		m = pat.match(t)
		if m:
			candidate = " ".join(m.group(1).split()).strip()
			if candidate:
				return candidate
	return t


def _find_content_root(soup: BeautifulSoup) -> Tag:
	# Prefer the canonical WP container.
	node = soup.find("div", class_="entry-content")
	if isinstance(node, Tag):
		return node

	# Fallbacks (other WP themes)
	for selector in ("article", "main", "body"):
		n = soup.select_one(selector)
		if isinstance(n, Tag):
			return n

	raise SystemExit("Could not find a content container in the fetched HTML")


def _clean_content_root(root: Tag) -> None:
	# Remove common non-story parts.
	for tag in root.find_all(
		[
			"script",
			"style",
			"table",
			"ins",
			"iframe",
			"form",
			"button",
			"nav",
			"noscript",
		]
	):
		tag.decompose()

	# Some WP themes include social/share blocks with these classes.
	for tag in root.select(
		".sharedaddy, .jp-relatedposts, .wpcnt, .wpcnt-comment, .comment-respond, .comments-area"
	):
		if isinstance(tag, Tag):
			tag.decompose()


@dataclass
class ExtractedStory:
	title: str
	translator: str
	editors: str | None
	occurrence: str | None
	blocks: list[tuple[str, str]]
	# blocks: (kind, payload)
	# - ("p", escaped text)
	# - ("xhtml", trusted inline XHTML for a <p> inner, e.g. <strong>Heading</strong>)
	# - ("img", local filename to reference from an <img src="..."/>)


def _normalize_label(key: str) -> str:
	k = key.strip().lower()
	if k in {"tl", "translated by", "translation", "translator"}:
		return "translator"
	if k in {"editor", "editors", "editing"}:
		return "editors"
	if k == "occurrence":
		return "occurrence"
	return k


def _text_from_tag(tag: Tag) -> str:
	# Convert <br> to newlines to allow splitting.
	for br in tag.find_all("br"):
		br.replace_with("\n")
	text = tag.get_text("", strip=False)
	# Normalize NBSP and whitespace.
	text = text.replace("\xa0", " ")
	return text


def _sanitize_asset_basename(name: str) -> str:
	stem = "".join(re.findall(r"[a-z0-9]+", name.lower()))
	return stem or "image"


def _guess_ext_from_url(url: str) -> str | None:
	path = urlparse(url).path
	if not path:
		return None
	base = path.rsplit("/", 1)[-1]
	if "." not in base:
		return None
	ext = "." + base.rsplit(".", 1)[-1].lower()
	if len(ext) <= 1 or len(ext) > 6:
		return None
	return ext


def _choose_local_image_name(*, story_title: str, index: int, src_url: str, out_dir: Path) -> str:
	base = _sanitize_asset_basename(story_title)
	ext = _guess_ext_from_url(src_url)
	if not ext:
		ext = ".jpg"
	# Keep canonical-ish names: storytitle.jpeg or storytitle2.jpeg ...
	suffix = "" if index == 1 else str(index)
	candidate = f"{base}{suffix}{ext}"

	# Avoid collisions.
	n = 2
	while (out_dir / candidate).exists():
		candidate = f"{base}{suffix}{n}{ext}"
		n += 1
	return candidate


def _download_image(*, src_url: str, out_path: Path) -> None:
	r = requests.get(src_url, headers=HEADERS, timeout=30, stream=True)
	r.raise_for_status()

	content_type = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
	if out_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
		final_path = out_path
	else:
		guessed = mimetypes.guess_extension(content_type) if content_type else None
		final_path = out_path.with_suffix(guessed or ".jpg")

	final_path.parent.mkdir(parents=True, exist_ok=True)
	with final_path.open("wb") as f:
		for chunk in r.iter_content(chunk_size=1024 * 64):
			if chunk:
				f.write(chunk)


def _img_src_from_tag(img: Tag) -> str | None:
	# Handle lazy-load patterns.
	for attr in ("src", "data-src", "data-lazy-src"):
		v = img.get(attr)
		if isinstance(v, str) and v.strip():
			return v.strip()
	return None


def _split_into_paras(text: str) -> list[str]:
	# Split on explicit newlines (often created from <br>) and blank lines.
	raw = re.split(r"\n{2,}|\r\n{2,}", text)
	out: list[str] = []
	for chunk in raw:
		for line in chunk.split("\n"):
			s = " ".join(line.split()).strip()
			if not s:
				continue
			out.append(s)
	return out


def _iter_story_blocks(root: Tag) -> Iterable[Tag]:
	# CSS selection preserves document order.
	for t in root.select("p, h2, h3, hr"):
		if isinstance(t, Tag):
			yield t


def _extract_story(
	*,
	url: str,
	html: str,
	title_override: str | None,
	translator_override: str | None,
	download_images: bool,
	images_out_dir: Path | None,
) -> tuple[ExtractedStory, list[Path]]:
	soup = BeautifulSoup(html, _pick_bs4_parser())
	raw_title = title_override or _extract_title(soup) or "Untitled"
	page_title = raw_title if title_override else _cleanup_title(raw_title)

	root = _find_content_root(soup)
	_clean_content_root(root)

	translator: str | None = translator_override
	editors: str | None = None
	occurrence: str | None = None
	blocks: list[tuple[str, str]] = []
	downloaded_paths: list[Path] = []

	img_index = 0

	for block in _iter_story_blocks(root):
		name = block.name.lower()

		if name == "hr":
			# Represent scene breaks using a simple marker paragraph.
			# (We keep the required outer <hr/> separators for metadata/end separately.)
			blocks.append(("p", escape("* * *")))
			continue

		if name in {"h2", "h3"}:
			heading = " ".join(block.get_text(" ", strip=True).split())
			if heading:
				blocks.append(("xhtml", f"<strong>{escape(heading)}</strong>"))
			continue

		if name != "p":
			continue

		# Pull any images first, then remove them so they don't pollute text extraction.
		imgs = list(block.find_all("img"))
		if imgs:
			for img in imgs:
				src = _img_src_from_tag(img)
				if not src:
					continue
				abs_src = urljoin(url, src)
				if download_images:
					out_dir = images_out_dir
					if out_dir is None:
						raise SystemExit("Internal error: images_out_dir is required when download_images is True")
					img_index += 1
					local_name = _choose_local_image_name(
						story_title=page_title,
						index=img_index,
						src_url=abs_src,
						out_dir=out_dir,
					)
					local_path = out_dir / local_name
					_download_image(src_url=abs_src, out_path=local_path)
					downloaded_paths.append(local_path)
					blocks.append(("img", local_path.name))
				else:
					# Keep the <img> but reference the original URL.
					blocks.append(("xhtml", f'<img src="{escape(abs_src)}" title=""/>' ))

			for img in imgs:
				img.decompose()

		text = _text_from_tag(block)
		for para_text in _split_into_paras(text):
			# Capture metadata-like lines if they appear in the story content.
			m = _METADATA_LINE_RE.match(para_text)
			if m:
				key = _normalize_label(m.group(1))
				value = m.group(2).strip()
				if key == "translator" and not translator and value:
					translator = value
					continue
				if key == "editors" and not editors and value:
					editors = value
					continue
				if key == "occurrence" and not occurrence and value:
					occurrence = value
					continue

			# Skip obvious navigation/footer junk.
			lowered = para_text.strip().lower()
			if lowered in {
				"like this:",
				"related",
				"posted in",
				"short stories directory",
				"back",
				"next",
				"previous",
				"leave a reply",
				"reply",
			}:
				continue

			if "short stories directory" in lowered:
				continue

			# Some themes include barebones nav text like "← Previous" / "Next →".
			if re.fullmatch(r"[←\s]*previous[\s→]*", lowered) or re.fullmatch(r"[←\s]*next[\s→]*", lowered):
				continue

			# Skip if it's just the page title repeated as a paragraph.
			if para_text.strip() == page_title.strip():
				continue

			blocks.append(("p", escape(para_text)))

	if not translator:
		translator = "Unknown"

	# Remove consecutive duplicates (common when sites repeat the title).
	deduped: list[tuple[str, str]] = []
	for b in blocks:
		if deduped and deduped[-1] == b:
			continue
		deduped.append(b)

	# Strip common blog intro text that appears before a scene break.
	# Example: announcements like "Sorry for the delay..." followed by "* * *".
	def looks_like_scene_break(s: str) -> bool:
		return " ".join(re.sub(r"<[^>]+>", "", s).split()).strip() in {"* * *", "***"}

	def strip_tags(s: str) -> str:
		return re.sub(r"<[^>]+>", "", s)

	intro_keywords = {
		"sorry",
		"delay",
		"schedule",
		"release",
		"chapter",
		"next week",
		"in the meantime",
		"tide you over",
		"patreon",
		"donate",
		"donation",
	}
	first_break = next(
		(i for i, (k, s) in enumerate(deduped) if k in {"p", "xhtml"} and looks_like_scene_break(s)),
		None,
	)
	if first_break is not None and 0 < first_break <= 10:
		intro_text = " ".join(strip_tags(s) for (k, s) in deduped[:first_break] if k in {"p", "xhtml"}).lower()
		if any(k in intro_text for k in intro_keywords):
			deduped = deduped[first_break + 1 :]

	# Trim leading/trailing scene-break markers.
	while deduped and deduped[0][0] in {"p", "xhtml"} and re.fullmatch(r"\*\s*\*\s*\*", deduped[0][1]):
		deduped.pop(0)
	while deduped and deduped[-1][0] in {"p", "xhtml"} and re.fullmatch(r"\*\s*\*\s*\*", deduped[-1][1]):
		deduped.pop()

	# If the post ends with an illustration, some sites add a scene-break marker
	# right before the image. Drop it when it's purely an "ending image" prelude.
	last_non_img = len(deduped) - 1
	while last_non_img >= 0 and deduped[last_non_img][0] == "img":
		last_non_img -= 1
	if last_non_img >= 0 and last_non_img < len(deduped) - 1:
		k, s = deduped[last_non_img]
		if k in {"p", "xhtml"} and re.fullmatch(r"\*\s*\*\s*\*", s):
			deduped.pop(last_non_img)

	if not deduped:
		raise SystemExit(
			"No story paragraphs were extracted. The site structure may not match the scraper. "
			"Try a different URL or update the selectors in tools/pull_story_from_web.py"
		)

	return (
		ExtractedStory(
		title=page_title,
		translator=translator,
		editors=editors,
		occurrence=occurrence,
		blocks=deduped,
		),
		downloaded_paths,
	)


def _render_story_xhtml(
	*,
	story: ExtractedStory,
	add_localization_credit: bool,
	localization_credit_line: str,
	editors_override: str | None,
	occurrence_override: str | None,
) -> str:
	title = story.title
	translator = story.translator
	editors = editors_override if editors_override is not None else story.editors
	occurrence = occurrence_override if occurrence_override is not None else story.occurrence

	lines: list[str] = []
	lines.append("<?xml version='1.0' encoding='utf-8'?>")
	lines.append(
		'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="en" xml:lang="en">'
	)
	lines.append("")
	lines.append("<head>")
	lines.append(f"  <title>{escape(title)}</title>")
	lines.append("</head>")
	lines.append("")
	lines.append("<body>")
	lines.append("")
	lines.append(f"  <h1>{escape(title)}</h1>")
	lines.append("")

	# Metadata block (see XHTML_STRUCTURE_GUIDE.md)
	lines.append(f"  <p>Translator: {escape(translator)}</p>")
	lines.append("")
	if editors:
		lines.append(f"  <p>Editors: {escape(editors)}</p>")
		lines.append("")
	if add_localization_credit:
		# Expect caller to pass a full <p>…</p> line.
		lines.append(f"  {localization_credit_line.strip()}")
		lines.append("")
	if occurrence:
		lines.append(f"  <p>Occurrence: {escape(occurrence)}</p>")
		lines.append("")

	lines.append("  <hr/>")
	lines.append("")

	for kind, payload in story.blocks:
		if kind == "img":
			lines.append("  <p>")
			lines.append(f"    <img src=\"{escape(payload)}\" title=\"\"/>")
			lines.append("  </p>")
			lines.append("")
			continue

		if kind == "xhtml":
			lines.append(f"  <p>{payload}</p>")
			lines.append("")
			continue

		# Default: paragraph text is escaped already.
		lines.append(f"  <p>{payload}</p>")
		lines.append("")

	lines.append("  <hr/>")
	lines.append("")
	lines.append("</body>")
	lines.append("")
	lines.append("</html>")
	lines.append("")
	return "\n".join(lines)


def _validate_xml_well_formed(xhtml: str) -> None:
	import xml.etree.ElementTree as ET

	# Parse from bytes to accept the XML prolog.
	try:
		ET.fromstring(xhtml.encode("utf-8"))
	except ET.ParseError as e:
		raise SystemExit(f"Generated XHTML is not well-formed XML: {e}")


def main(argv: list[str]) -> int:
	ap = argparse.ArgumentParser(description="Fetch a web short story and write a story XHTML file.")
	ap.add_argument("url", help="URL of the story page")

	ap.add_argument(
		"--epub-dir",
		type=Path,
		default=_repo_root() / "Unchanged-Translations" / "EPUB",
		help="Where to write the XHTML file when --out is not provided (default: English-Localized/EPUB)",
	)
	ap.add_argument(
		"--out",
		type=Path,
		default=None,
		help="Explicit output .xhtml path. If omitted, filename is derived from title and written under --epub-dir.",
	)

	ap.add_argument("--title", default=None, help="Override the extracted page title")
	ap.add_argument("--translator", default=None, help="Override translator metadata (default: try to infer, else 'Unknown')")
	ap.add_argument("--editors", default=None, help="Set Editors metadata line")
	ap.add_argument("--occurrence", default=None, help="Set Occurrence metadata line")

	ap.add_argument(
		"--download-images",
		action="store_true",
		help="Download <img> assets found in the story content and rewrite XHTML to reference local files.",
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

	ap.add_argument("--force", action="store_true", help="Overwrite output file if it already exists")
	ap.add_argument("--no-xml-check", action="store_true", help="Skip XML well-formedness check")

	args = ap.parse_args(argv)

	if args.out is None:
		filename = _slugify_story_filename(args.title or "")
		# If title wasn't provided, filename will get overwritten after extraction.
		# We'll pick the final output path later.
		out_path = args.epub_dir / filename
	else:
		out_path = args.out

	html = _fetch_html(args.url)
	# If downloading images, place them next to the output XHTML in the EPUB folder.
	images_out_dir: Path | None = None
	if args.download_images:
		images_out_dir = out_path.parent

	story, downloaded_images = _extract_story(
		url=args.url,
		html=html,
		title_override=args.title,
		translator_override=args.translator,
		download_images=args.download_images,
		images_out_dir=images_out_dir,
	)

	if args.out is None:
		out_path = args.epub_dir / _slugify_story_filename(story.title)

	out_path.parent.mkdir(parents=True, exist_ok=True)
	if out_path.exists() and not args.force:
		raise SystemExit(f"Refusing to overwrite existing file (use --force): {out_path}")

	xhtml = _render_story_xhtml(
		story=story,
		add_localization_credit=args.add_localization_credit,
		localization_credit_line=args.localization_credit_line,
		editors_override=args.editors,
		occurrence_override=args.occurrence,
	)

	if not args.no_xml_check:
		_validate_xml_well_formed(xhtml)

	out_path.write_text(xhtml, encoding="utf-8")

	print(f"Wrote: {out_path}")
	print(f"Title: {story.title}")
	print(f"Translator: {story.translator}")
	if story.editors:
		print(f"Editors (inferred): {story.editors}")
	if story.occurrence:
		print(f"Occurrence (inferred): {story.occurrence}")
	if downloaded_images:
		print(f"Downloaded images: {len(downloaded_images)}")
		for p in downloaded_images:
			print(p.as_posix())
	return 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))

