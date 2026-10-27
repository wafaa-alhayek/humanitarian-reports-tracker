"""Download PDFs and turn them into plain text."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Optional

import requests
from pypdf import PdfReader

from .sources.reliefweb import HEADERS

MAX_PDF_BYTES = 40 * 1024 * 1024


def download(url: str, cache_dir: str) -> Optional[bytes]:
    """Return the file's bytes, caching by URL so reruns don't download again."""
    if not url.startswith("http"):
        path = Path(url)
        return path.read_bytes() if path.exists() else None
    cache = Path(cache_dir) / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".pdf")
    if cache.exists():
        return cache.read_bytes()
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    if len(resp.content) > MAX_PDF_BYTES:
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(resp.content)
    return resp.content


def pdf_to_text(data: bytes, max_pages: int = 40) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            pages.append(f"[page {i + 1}]\n" + (page.extract_text() or ""))
        except Exception:  # a broken page shouldn't sink the whole report
            continue
    return clean("\n".join(pages))


def clean(text: str) -> str:
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def detect_language(text: str) -> str:
    arabic = len(re.findall(r"[؀-ۿ]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return "ar" if arabic > latin else "en"
