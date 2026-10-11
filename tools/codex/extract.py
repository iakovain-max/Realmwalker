"""Dump the text layer of Anton's three D&D books, one file per page, for searching.

    .venv\\Scripts\\python.exe tools\\codex\\extract.py            (all three books)
    .venv\\Scripts\\python.exe tools\\codex\\extract.py --book mm  (one of them)
    .venv\\Scripts\\python.exe tools\\codex\\extract.py --render mm 120 121   (page images, to check numbers)

The books are scans with a noisy OCR layer: use the text to find things, and the page images to check every number.
Everything goes to build/codex/ (git-ignored); nothing from the books may enter a committed file. The books' folder
is only ever read.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "codex"
BOOKS_DIR = Path(r"C:\Users\Alpine\Desktop\5.5e DND")
BOOKS = {
    "phb": "Player's Handbook 5-5e.pdf",
    "dmg": "Dungeon_Masters_Guide_-_Wizards_of_the_Coast.pdf",
    "mm": "Monster Manual.pdf",
}


def book_path(key: str, books_dir: Path = BOOKS_DIR) -> Path:
    return books_dir / BOOKS[key]


def extract(key: str, books_dir: Path = BOOKS_DIR, force: bool = False) -> int:
    """Write build/codex/<key>/p###.txt for every page (PDF page numbers, from 1). Returns the page count."""
    from pypdf import PdfReader

    src = book_path(key, books_dir)
    if not src.exists():
        print(f"{key}: not found at {src}", file=sys.stderr)
        return 0
    out = OUT / key
    out.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(src))
    count = len(reader.pages)
    for i, page in enumerate(reader.pages, start=1):
        target = out / f"p{i:03d}.txt"
        if target.exists() and not force:
            continue
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # a broken page must not stop the rest
            text = f"<<could not read this page: {exc}>>"
        target.write_text(text, encoding="utf-8")
    print(f"{key}: {count} pages -> {out}")
    return count


def render(key: str, pages: list[int], books_dir: Path = BOOKS_DIR, scale: float = 2.0) -> list[Path]:
    """Render PDF pages (numbers from 1) to build/codex/pages/<key>_p###.png for checking numbers by eye."""
    import pypdfium2 as pdfium

    out = OUT / "pages"
    out.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(book_path(key, books_dir)))
    made = []
    try:
        for n in pages:
            target = out / f"{key}_p{n:03d}.png"
            if not target.exists():
                bitmap = pdf[n - 1].render(scale=scale)
                bitmap.to_pil().save(target)
            made.append(target)
    finally:
        pdf.close()
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", choices=sorted(BOOKS), help="only this book")
    ap.add_argument("--books-dir", type=Path, default=BOOKS_DIR)
    ap.add_argument("--force", action="store_true", help="extract pages already extracted again")
    ap.add_argument("--render", nargs="+", metavar=("BOOK", "PAGE"), help="render pages to PNG: BOOK PAGE [PAGE...]")
    args = ap.parse_args(argv)
    if args.render:
        key, *nums = args.render
        for p in render(key, [int(n) for n in nums], args.books_dir):
            print(p)
        return 0
    for key in [args.book] if args.book else BOOKS:
        extract(key, args.books_dir, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
