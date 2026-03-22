#!/usr/bin/env python3
"""
ebook_to_kb.py — Convert PDF/EPUB ebooks into a structured KB folder.

Usage:
    python ebook_to_kb.py book.pdf
    python ebook_to_kb.py book.epub
    python ebook_to_kb.py book.pdf --output ~/kb/architecture
    python ebook_to_kb.py book.pdf --max-chunk-lines 300

Output structure:
    {book-slug}/
    ├── index.md                  # Human-readable TOC with summaries
    ├── kb-entry.yaml             # Paste this into kb-registry.yaml
    └── chapters/
        ├── 01-introduction/
        │   └── content.md
        ├── 02-chapter-title/
        │   ├── 01-section.md
        │   └── 02-section.md
        └── ...
"""

import re
import sys
import os
import argparse
import textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class Section:
    title: str
    level: int          # 1 = chapter, 2 = section, 3 = subsection
    content: str = ""
    children: list = field(default_factory=list)
    page_start: Optional[int] = None


@dataclass
class BookMeta:
    title: str
    author: str
    subject: str = ""
    source_file: str = ""
    total_pages: int = 0


# ─── Slug / Path Helpers ──────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def zero_pad(n: int, total: int) -> str:
    width = max(2, len(str(total)))  # always at least 2 digits for clean sorting
    return str(n).zfill(width)


# ─── PDF Processing ───────────────────────────────────────────────────────────

def extract_pdf_outline(reader) -> list[dict]:
    """Extract bookmarks/outline from PDF. Returns flat list with levels."""
    outline = []

    def walk(items, level=1):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
            else:
                try:
                    page_num = reader.get_destination_page_number(item)
                    outline.append({
                        "title": item.title,
                        "level": level,
                        "page": page_num
                    })
                except Exception:
                    pass

    try:
        walk(reader.outline)
    except Exception:
        pass

    return outline


def detect_headings_from_text(pages_text: list[str]) -> list[dict]:
    """
    Fallback: detect chapter/section headings from text patterns.
    Looks for: ALL CAPS lines, 'Chapter N', numbered headings, short isolated lines.
    """
    headings = []
    chapter_patterns = [
        re.compile(r"^(chapter|part|section)\s+(\d+|[ivxlcdm]+)[:\s]", re.IGNORECASE),
        re.compile(r"^\d+\.\s+[A-Z][a-zA-Z\s]{3,60}$"),
        re.compile(r"^[A-Z][A-Z\s]{4,50}$"),
    ]

    for page_num, text in enumerate(pages_text):
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            for pat in chapter_patterns:
                if pat.match(line):
                    # Determine level
                    level = 1 if re.match(r"^(chapter|part)\s", line, re.IGNORECASE) else 2
                    headings.append({
                        "title": line,
                        "level": level,
                        "page": page_num
                    })
                    break

    return headings


def process_pdf(filepath: Path) -> tuple[BookMeta, list[Section]]:
    import pdfplumber
    from pypdf import PdfReader

    print(f"  📖 Reading PDF: {filepath.name}")

    reader = PdfReader(str(filepath))
    meta_raw = reader.metadata or {}

    meta = BookMeta(
        title=meta_raw.get("/Title", filepath.stem) or filepath.stem,
        author=meta_raw.get("/Author", "Unknown") or "Unknown",
        subject=meta_raw.get("/Subject", "") or "",
        source_file=filepath.name,
        total_pages=len(reader.pages),
    )

    print(f"  📚 Title: {meta.title} | Author: {meta.author} | Pages: {meta.total_pages}")

    # Extract all text per page
    print(f"  📄 Extracting text from {meta.total_pages} pages...")
    pages_text = []
    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    # Try outline first, fall back to heading detection
    outline = extract_pdf_outline(reader)
    if len(outline) < 3:
        print(f"  ⚠️  No PDF outline found — detecting headings from text")
        outline = detect_headings_from_text(pages_text)

    print(f"  🗂️  Found {len(outline)} outline entries")

    # Build sections by assigning page ranges
    sections = []
    for i, entry in enumerate(outline):
        page_start = entry["page"]
        page_end = outline[i + 1]["page"] if i + 1 < len(outline) else len(pages_text)
        content = "\n\n".join(pages_text[page_start:page_end]).strip()
        sections.append(Section(
            title=entry["title"],
            level=entry["level"],
            content=content,
            page_start=page_start + 1,
        ))

    # If no sections found, treat whole book as one section per N pages
    if not sections:
        print(f"  ⚠️  No headings detected — splitting by every 20 pages")
        chunk = 20
        for i in range(0, len(pages_text), chunk):
            content = "\n\n".join(pages_text[i:i + chunk]).strip()
            sections.append(Section(
                title=f"Pages {i + 1}–{min(i + chunk, len(pages_text))}",
                level=1,
                content=content,
                page_start=i + 1,
            ))

    return meta, sections


# ─── EPUB Processing ──────────────────────────────────────────────────────────

def process_epub(filepath: Path) -> tuple[BookMeta, list[Section]]:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    print(f"  📖 Reading EPUB: {filepath.name}")

    book = epub.read_epub(str(filepath))

    meta = BookMeta(
        title=book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else filepath.stem,
        author=book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else "Unknown",
        subject=book.get_metadata("DC", "subject")[0][0] if book.get_metadata("DC", "subject") else "",
        source_file=filepath.name,
    )

    print(f"  📚 Title: {meta.title} | Author: {meta.author}")

    sections = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")

        # Find main heading
        heading = soup.find(["h1", "h2", "h3"])
        if not heading:
            # Skip nav/toc/cover documents
            body_text = soup.get_text(separator="\n", strip=True)
            if len(body_text) < 100:
                continue
            title = item.get_name().split("/")[-1].replace(".xhtml", "").replace(".html", "")
        else:
            title = heading.get_text(strip=True)
            level = int(heading.name[1])  # h1→1, h2→2

        # Convert HTML to clean markdown-ish text
        content = html_to_markdown(soup)

        if content.strip():
            level = 1 if heading and heading.name == "h1" else 2
            sections.append(Section(
                title=title,
                level=level,
                content=content,
            ))

    print(f"  🗂️  Found {len(sections)} sections")
    return meta, sections


def html_to_markdown(soup) -> str:
    """Convert BeautifulSoup to clean markdown text."""
    from bs4 import NavigableString, Tag

    lines = []

    def walk(el, depth=0):
        if isinstance(el, NavigableString):
            text = str(el).strip()
            if text:
                lines.append(text)
            return

        tag = el.name if isinstance(el, Tag) else None

        if tag in ("h1", "h2", "h3", "h4"):
            level = int(tag[1])
            prefix = "#" * level
            text = el.get_text(strip=True)
            if text:
                lines.append(f"\n{prefix} {text}\n")
            return

        if tag == "p":
            text = el.get_text(separator=" ", strip=True)
            if text:
                lines.append(f"\n{text}\n")
            return

        if tag in ("ul", "ol"):
            for li in el.find_all("li", recursive=False):
                text = li.get_text(separator=" ", strip=True)
                lines.append(f"- {text}")
            lines.append("")
            return

        if tag == "blockquote":
            text = el.get_text(separator=" ", strip=True)
            lines.append(f"\n> {text}\n")
            return

        if tag in ("script", "style", "nav", "head"):
            return

        for child in el.children:
            walk(child, depth)

    walk(soup.find("body") or soup)
    return "\n".join(lines).strip()


# ─── Hierarchy Builder ────────────────────────────────────────────────────────

def build_hierarchy(sections: list[Section]) -> list[Section]:
    """
    Nest level-2+ sections as children of the nearest level-1 parent.
    Returns top-level sections only (children embedded).
    """
    roots = []
    current_chapter = None

    for s in sections:
        if s.level == 1:
            roots.append(s)
            current_chapter = s
        else:
            if current_chapter:
                current_chapter.children.append(s)
            else:
                # Promote to root if no parent found
                roots.append(s)

    return roots


# ─── Chunker ─────────────────────────────────────────────────────────────────

def split_large_section(section: Section, max_lines: int) -> list[Section]:
    """Split oversized sections into sub-chunks."""
    lines = section.content.split("\n")
    if len(lines) <= max_lines:
        return [section]

    chunks = []
    for i, chunk_lines in enumerate(
        [lines[j:j + max_lines] for j in range(0, len(lines), max_lines)]
    ):
        chunks.append(Section(
            title=f"{section.title} (part {i + 1})",
            level=section.level,
            content="\n".join(chunk_lines),
            page_start=section.page_start,
        ))
    return chunks


# ─── Writer ──────────────────────────────────────────────────────────────────

def write_section_file(path: Path, section: Section, book_meta: BookMeta):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {section.title}",
        "",
        f"> Source: {book_meta.title} — {book_meta.author}",
    ]
    if section.page_start:
        lines.append(f"> Pages: ~{section.page_start}")
    lines += ["", "---", "", section.content.strip(), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_output(
    meta: BookMeta,
    sections: list[Section],
    output_dir: Path,
    max_chunk_lines: int,
):
    book_slug = slugify(meta.title)
    book_dir = output_dir / book_slug
    chapters_dir = book_dir / "chapters"
    book_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)

    hierarchy = build_hierarchy(sections)
    total_chapters = len(hierarchy)

    toc_entries = []  # For index.md
    kb_sources = []   # For kb-entry.yaml

    print(f"\n  ✍️  Writing to: {book_dir}")

    for ch_idx, chapter in enumerate(hierarchy, 1):
        ch_num = zero_pad(ch_idx, total_chapters)
        ch_slug = slugify(chapter.title)
        ch_dir = chapters_dir / f"{ch_num}-{ch_slug}"

        if chapter.children:
            # Has sub-sections → directory with one file per section
            ch_dir.mkdir(parents=True, exist_ok=True)

            # Write chapter intro (content before first child section)
            if chapter.content.strip():
                intro_path = ch_dir / "00-intro.md"
                write_section_file(intro_path, chapter, meta)

            section_topics = []
            for s_idx, section in enumerate(chapter.children, 1):
                s_num = zero_pad(s_idx, len(chapter.children))
                s_slug = slugify(section.title)

                # Chunk if too large
                chunks = split_large_section(section, max_chunk_lines)
                for c_idx, chunk in enumerate(chunks):
                    suffix = f"-part{c_idx + 1}" if len(chunks) > 1 else ""
                    filepath = ch_dir / f"{s_num}-{s_slug}{suffix}.md"
                    write_section_file(filepath, chunk, meta)

                section_topics.append(section.title.lower())

            toc_entries.append({
                "chapter": chapter.title,
                "dir": f"chapters/{ch_num}-{ch_slug}/",
                "sections": [s.title for s in chapter.children],
            })
            kb_sources.append({
                "title": f"{meta.title} — {chapter.title}",
                "file": f"{book_slug}/chapters/{ch_num}-{ch_slug}/",
                "topics": section_topics[:8],  # cap topics list
            })

        else:
            # No sub-sections → single file
            chunks = split_large_section(chapter, max_chunk_lines)
            for c_idx, chunk in enumerate(chunks):
                suffix = f"-part{c_idx + 1}" if len(chunks) > 1 else ""
                filepath = chapters_dir / f"{ch_num}-{ch_slug}{suffix}.md"
                write_section_file(filepath, chunk, meta)

            toc_entries.append({
                "chapter": chapter.title,
                "file": f"chapters/{ch_num}-{ch_slug}.md",
                "sections": [],
            })
            kb_sources.append({
                "title": f"{meta.title} — {chapter.title}",
                "file": f"{book_slug}/chapters/{ch_num}-{ch_slug}.md",
                "topics": [slugify(chapter.title)],
            })

    # ── index.md ──────────────────────────────────────────────────────────────
    index_lines = [
        f"# {meta.title}",
        "",
        f"> **Author**: {meta.author}  ",
        f"> **Source**: {meta.source_file}  ",
        f"> **Chapters**: {total_chapters}  ",
        "",
        "---",
        "",
        "## Table of Contents",
        "",
    ]
    for entry in toc_entries:
        if entry.get("file"):
            index_lines.append(f"- [{entry['chapter']}]({entry['file']})")
        else:
            index_lines.append(f"- **{entry['chapter']}** (`{entry['dir']}`)")
            for s in entry["sections"]:
                index_lines.append(f"  - {s}")
    index_lines += [
        "",
        "---",
        "",
        "## KB Entry",
        "",
        "Add the contents of `kb-entry.yaml` to your `kb-registry.yaml` sources list.",
    ]
    (book_dir / "index.md").write_text("\n".join(index_lines), encoding="utf-8")

    # ── kb-entry.yaml ─────────────────────────────────────────────────────────
    # Collect all unique topics across chapters for the KB-level keywords
    all_topics = list({
        topic
        for src in kb_sources
        for topic in src.get("topics", [])
    })

    kb_entry = {
        "# ADD THIS TO YOUR kb-registry.yaml": None,
        "id": slugify(meta.title),
        "name": meta.title,
        "description": f"Knowledge base for '{meta.title}' by {meta.author}",
        "keywords": all_topics[:15],
        "sources": kb_sources,
    }

    # Manual YAML to keep comments
    yaml_lines = [
        f"# Paste this into the 'knowledge_bases' list in kb-registry.yaml",
        f"",
        f"- id: {slugify(meta.title)}",
        f"  name: \"{meta.title}\"",
        f"  description: \"Knowledge base for '{meta.title}' by {meta.author}\"",
        f"  keywords:",
    ]
    for kw in all_topics[:15]:
        yaml_lines.append(f"    - {kw}")
    yaml_lines.append("  sources:")
    for src in kb_sources:
        yaml_lines.append(f"    - title: \"{src['title']}\"")
        yaml_lines.append(f"      file: \"{src['file']}\"")
        yaml_lines.append(f"      topics: {src['topics']}")

    (book_dir / "kb-entry.yaml").write_text("\n".join(yaml_lines), encoding="utf-8")

    return book_dir, total_chapters, len(sections)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF/EPUB ebooks into a structured KB markdown folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python ebook_to_kb.py book.pdf
              python ebook_to_kb.py book.epub --output ~/kb/architecture
              python ebook_to_kb.py book.pdf --max-chunk-lines 200
        """),
    )
    parser.add_argument("input", help="Path to PDF or EPUB file")
    parser.add_argument(
        "--output", "-o",
        default="./kb-output",
        help="Output directory (default: ./kb-output)",
    )
    parser.add_argument(
        "--max-chunk-lines",
        type=int,
        default=300,
        help="Max lines per markdown file before splitting (default: 300)",
    )

    args = parser.parse_args()

    filepath = Path(args.input).expanduser().resolve()
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    output_dir = Path(args.output).expanduser().resolve()
    ext = filepath.suffix.lower()

    print(f"\n{'='*55}")
    print(f"  ebook_to_kb — {filepath.name}")
    print(f"{'='*55}")

    if ext == ".pdf":
        meta, sections = process_pdf(filepath)
    elif ext == ".epub":
        meta, sections = process_epub(filepath)
    else:
        print(f"❌ Unsupported format: {ext}  (supported: .pdf, .epub)")
        sys.exit(1)

    if not sections:
        print("❌ No content extracted. The file may be scanned/image-based.")
        print("   Try OCR first: pip install ocrmypdf && ocrmypdf input.pdf input-ocr.pdf")
        sys.exit(1)

    book_dir, n_chapters, n_sections = write_output(
        meta, sections, output_dir, args.max_chunk_lines
    )

    print(f"\n{'='*55}")
    print(f"  ✅ Done!")
    print(f"{'='*55}")
    print(f"  📁 Output:    {book_dir}")
    print(f"  📚 Chapters:  {n_chapters}")
    print(f"  📄 Sections:  {n_sections}")
    print(f"  📋 Index:     {book_dir}/index.md")
    print(f"  🗂️  KB Entry:  {book_dir}/kb-entry.yaml")
    print(f"\n  Next steps:")
    print(f"  1. Review the output in {book_dir}/")
    print(f"  2. Copy contents of kb-entry.yaml into your kb-registry.yaml")
    print(f"  3. Use ask-kb or consult-kb to query the knowledge base")
    print()


if __name__ == "__main__":
    main()
