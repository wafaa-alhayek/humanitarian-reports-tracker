"""Settings read from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass
class Settings:
    # Which model extracts facts: gemini, ollama or rules (offline, no AI)
    llm: str = field(default_factory=lambda: os.getenv("LLM_BACKEND", "gemini"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
    # Characters of report text sent to the model. Local models get less.
    max_chars: int = field(default_factory=lambda: int(os.getenv("MAX_CHARS", "40000")))

    # Where results go: duckdb (local file) or bigquery
    store: str = field(default_factory=lambda: os.getenv("STORE", "duckdb"))
    duckdb_path: str = field(default_factory=lambda: os.getenv("DUCKDB_PATH", "data/reports.duckdb"))
    bq_project: str = field(default_factory=lambda: os.getenv("BQ_PROJECT", ""))
    bq_dataset: str = field(default_factory=lambda: os.getenv("BQ_DATASET", "humanitarian_reports"))
    bq_location: str = field(default_factory=lambda: os.getenv("BQ_LOCATION", "EU"))

    # ReliefWeb's JSON API needs an approved appname; the RSS feed does not.
    reliefweb_appname: str = field(default_factory=lambda: os.getenv("RELIEFWEB_APPNAME", ""))
    pdf_cache: str = field(default_factory=lambda: os.getenv("PDF_CACHE", "data/pdfs"))
