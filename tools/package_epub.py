#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


def _iter_files(root: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == ".DS_Store" or rel.endswith("/.DS_Store"):
            continue
        files.append((path, rel))
    files.sort(key=lambda x: x[1])
    return files


def package_epub(*, src_dir: Path, out_file: Path) -> None:
    if not src_dir.exists() or not src_dir.is_dir():
        raise SystemExit(f"Source directory not found: {src_dir}")

    mimetype_path = src_dir / "mimetype"
    if not mimetype_path.is_file():
        raise SystemExit(f"Missing required file: {mimetype_path}")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    # NOTE: EPUB spec requires the 'mimetype' entry to be first in the ZIP and
    # stored without compression.
    with zipfile.ZipFile(
        out_file,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        zf.write(mimetype_path, arcname="mimetype", compress_type=zipfile.ZIP_STORED)

        for path, rel in _iter_files(src_dir):
            if rel == "mimetype":
                continue
            zf.write(path, arcname=rel)

    # Basic sanity check
    with zipfile.ZipFile(out_file, mode="r") as zf:
        infos = zf.infolist()
        if not infos or infos[0].filename != "mimetype":
            raise SystemExit("Invalid EPUB: 'mimetype' is not the first ZIP entry")
        if infos[0].compress_type != zipfile.ZIP_STORED:
            raise SystemExit("Invalid EPUB: 'mimetype' is compressed (must be stored)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Package a local EPUB directory (mimetype/META-INF/EPUB/) into a .epub file."
    )
    parser.add_argument(
        "--src",
        required=True,
        type=Path,
        help="Source directory containing mimetype, META-INF/, and EPUB/",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output .epub path",
    )

    args = parser.parse_args(argv)
    package_epub(src_dir=args.src, out_file=args.out)
    print(f"Wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
