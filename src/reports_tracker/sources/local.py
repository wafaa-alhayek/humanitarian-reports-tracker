"""Use PDFs (or .txt files) already on disk, e.g. reports a partner emailed you."""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Iterator

from ..schema import Report


def fetch(folder: str, limit: int = 1000) -> Iterator[Report]:
    files = sorted(p for p in Path(folder).glob("**/*") if p.suffix.lower() in {".pdf", ".txt", ".md"})
    for path in files[:limit]:
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
        yield Report(
            report_id=digest,
            source="local",
            url=path.resolve().as_uri(),
            title=path.stem.replace("_", " ").replace("-", " "),
            published=date.fromtimestamp(path.stat().st_mtime).isoformat(),
            file_url=str(path) if path.suffix.lower() == ".pdf" else None,
            text="" if path.suffix.lower() == ".pdf" else path.read_text(errors="ignore"),
        )
