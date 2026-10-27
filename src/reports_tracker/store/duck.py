from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import FIGURE_COLUMNS, REPORT_COLUMNS

_DUCK_TYPES = {"STRING": "VARCHAR", "INT64": "BIGINT", "FLOAT64": "DOUBLE", "BOOL": "BOOLEAN",
               "DATE": "DATE", "TIMESTAMP": "TIMESTAMPTZ"}


def _ddl(name: str, cols: dict[str, str], key: str) -> str:
    body = ", ".join(f"{c} {_DUCK_TYPES[t]}" for c, t in cols.items())
    return f"CREATE TABLE IF NOT EXISTS {name} ({body}, PRIMARY KEY ({key}))"


class DuckStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with duckdb.connect(path) as con:
            con.execute(_ddl("reports", REPORT_COLUMNS, "report_id"))
            con.execute(_ddl("figures", FIGURE_COLUMNS, "report_id, figure_no"))

    def seen_ids(self) -> set[str]:
        with duckdb.connect(self.path, read_only=True) as con:
            return {r[0] for r in con.execute("SELECT report_id FROM reports").fetchall()}

    def save(self, report_row: dict, figure_rows: list[dict]) -> None:
        with duckdb.connect(self.path) as con:
            con.execute("BEGIN")
            rid = report_row["report_id"]
            con.execute("DELETE FROM figures WHERE report_id = ?", [rid])
            con.execute("DELETE FROM reports WHERE report_id = ?", [rid])
            cols = list(REPORT_COLUMNS)
            con.execute(f"INSERT INTO reports VALUES ({', '.join('?' * len(cols))})",
                        [report_row.get(c) for c in cols])
            fcols = list(FIGURE_COLUMNS)
            if figure_rows:
                con.executemany(f"INSERT INTO figures VALUES ({', '.join('?' * len(fcols))})",
                                [[r.get(c) for c in fcols] for r in figure_rows])
            con.execute("COMMIT")

    def reports(self) -> pd.DataFrame:
        with duckdb.connect(self.path, read_only=True) as con:
            return con.execute("SELECT * FROM reports ORDER BY published DESC").df()

    def figures(self) -> pd.DataFrame:
        with duckdb.connect(self.path, read_only=True) as con:
            return con.execute("SELECT * FROM figures ORDER BY published DESC, report_id, figure_no").df()
