"""Where processed reports live. DuckDB for a laptop, BigQuery for the team."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import pandas as pd

from ..config import Settings
from ..schema import Extraction, Report

REPORT_COLUMNS = {
    "report_id": "STRING", "source": "STRING", "url": "STRING", "title": "STRING",
    "published": "DATE", "organizations": "STRING", "countries": "STRING", "themes": "STRING",
    "file_url": "STRING", "language": "STRING", "n_chars": "INT64", "summary": "STRING",
    "report_type": "STRING", "locations": "STRING", "sectors": "STRING", "model": "STRING",
    "n_figures": "INT64", "n_verified": "INT64", "processed_at": "TIMESTAMP",
}
FIGURE_COLUMNS = {
    "report_id": "STRING", "figure_no": "INT64", "indicator": "STRING", "value": "FLOAT64",
    "unit": "STRING", "location": "STRING", "as_of_date": "STRING", "label": "STRING",
    "evidence": "STRING", "verified": "BOOL", "model": "STRING", "published": "DATE",
}


def _join(items: list[str]) -> str:
    return "; ".join(dict.fromkeys(i.strip() for i in items if i and i.strip()))


def to_rows(report: Report, ex: Extraction, model: str, verified: list[bool]) -> tuple[dict, list[dict]]:
    report_row = {
        "report_id": report.report_id, "source": report.source, "url": report.url,
        "title": report.title, "published": report.published,
        "organizations": _join(report.organizations), "countries": _join(report.countries),
        "themes": _join(report.themes), "file_url": report.file_url, "language": report.language,
        "n_chars": len(report.text), "summary": ex.summary, "report_type": ex.report_type,
        "locations": _join(ex.locations), "sectors": _join(ex.sectors), "model": model,
        "n_figures": len(ex.figures), "n_verified": sum(verified),
        "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    figure_rows = [
        {"report_id": report.report_id, "figure_no": i, **f.model_dump(), "verified": ok,
         "model": model, "published": report.published}
        for i, (f, ok) in enumerate(zip(ex.figures, verified))
    ]
    return report_row, figure_rows


class Store(Protocol):
    def seen_ids(self) -> set[str]: ...
    def save(self, report_row: dict, figure_rows: list[dict]) -> None: ...
    def reports(self) -> pd.DataFrame: ...
    def figures(self) -> pd.DataFrame: ...


def get_store(settings: Settings, kind: str | None = None) -> Store:
    kind = kind or settings.store
    if kind == "duckdb":
        from .duck import DuckStore
        return DuckStore(settings.duckdb_path)
    if kind == "bigquery":
        from .bq import BigQueryStore
        return BigQueryStore(settings.bq_project, settings.bq_dataset, settings.bq_location)
    raise ValueError(f"Unknown store {kind!r}; use duckdb or bigquery")
