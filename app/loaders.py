"""Turn raw files (HTML, PDF, DOCX, TXT/MD) into heading-aware sections."""

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from docx import Document as DocxDocument
from pypdf import PdfReader


warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass
class Section:
    text: str
    section: str = ""
    page: int | None = None


_WS = re.compile(r"[ \t\u00a0]+")
_SEC_ITEM = re.compile(r"^(item\s+\d+[a-z]?\.?)(\s|$)", re.I)
_BOILERPLATE = {
    "references", "notes", "external links", "further reading", "see also", "sources",
    "citations", "bibliography", "footnotes", "works cited", "explanatory notes",
}


def _clean(text: str) -> str:
    lines = [_WS.sub(" ", ln).strip() for ln in text.splitlines()]
    out, blank = [], 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank == 1:
                out.append("")
            continue
        blank = 0
        out.append(ln)
    return "\n".join(out).strip()


def load_html(path: Path) -> list[Section]:
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for table in soup.find_all("table"):
        if table.find_parent("table"):
            continue
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c and c not in ("$", "%", ")")]
            if cells:
                rows.append(" | ".join(cells))
        p = soup.new_tag("p")
        p.string = "\n".join(rows)
        table.replace_with(p)
    for ix in soup.select("ix\\:header, [style*='display:none']"):
        ix.decompose()
    for sup in soup.select("sup.reference, .mw-editsection, .navbox, .reflist"):
        sup.decompose()

    body = soup.body or soup
    sections: list[Section] = []
    current, buf = "Introduction", []

    def flush():
        text = _clean("\n".join(buf))
        if len(text) > 40:
            sections.append(Section(text=text, section=current))

    for el in body.find_all(["h1", "h2", "h3", "h4", "p", "div", "li", "span", "font"]):
        if el.find(["p", "div", "li", "h1", "h2", "h3", "h4"]):
            continue
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        is_heading = el.name in ("h1", "h2", "h3", "h4") or (
            len(txt) < 120 and _SEC_ITEM.match(txt)
        )
        if is_heading:
            flush()
            current, buf = txt[:120], []
        else:
            buf.append(txt)
    flush()
    seen, unique = set(), []
    for s in sections:
        key = s.text[:200]
        if s.section.lower().strip(" .") in _BOILERPLATE:
            continue
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def load_pdf(path: Path) -> list[Section]:
    reader = PdfReader(str(path))
    out = []
    for i, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        if len(text) > 40:
            out.append(Section(text=text, section=f"page {i}", page=i))
    return out


def load_docx(path: Path) -> list[Section]:
    doc = DocxDocument(str(path))
    sections, current, buf = [], "Introduction", []
    for para in doc.paragraphs:
        txt = para.text.strip()
        if not txt:
            continue
        if para.style.name.lower().startswith(("heading", "title")):
            if buf:
                sections.append(Section(text="\n".join(buf), section=current))
            current, buf = txt, []
        else:
            buf.append(txt)
    if buf:
        sections.append(Section(text="\n".join(buf), section=current))
    return sections


def load_text(path: Path) -> list[Section]:
    sections, current, buf = [], "Introduction", []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ln.startswith("#"):
            if buf:
                sections.append(Section(text=_clean("\n".join(buf)), section=current))
            current, buf = ln.lstrip("# ").strip(), []
        else:
            buf.append(ln)
    if buf:
        sections.append(Section(text=_clean("\n".join(buf)), section=current))
    return [s for s in sections if s.text]


LOADERS = {
    ".html": load_html,
    ".htm": load_html,
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".txt": load_text,
    ".md": load_text,
}


def load_file(path: Path) -> list[Section]:
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return loader(path)
