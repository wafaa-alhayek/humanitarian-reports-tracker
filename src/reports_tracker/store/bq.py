"""BigQuery store. Auth comes from Application Default Credentials
(`gcloud auth application-default login`, or a service account in CI)."""
from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

from . import FIGURE_COLUMNS, REPORT_COLUMNS


class BigQueryStore:
    def __init__(self, project: str, dataset: str, location: str = "EU"):
        if not project:
            raise ValueError("BQ_PROJECT is not set")
        self.client = bigquery.Client(project=project, location=location)
        self.ds = f"{project}.{dataset}"
        self.client.create_dataset(bigquery.Dataset(self.ds), exists_ok=True)
        for name, cols in (("reports", REPORT_COLUMNS), ("figures", FIGURE_COLUMNS)):
            schema = [bigquery.SchemaField(c, t) for c, t in cols.items()]
            table = bigquery.Table(f"{self.ds}.{name}", schema=schema)
            if name == "figures":
                table.time_partitioning = bigquery.TimePartitioning(field="published")
            self.client.create_table(table, exists_ok=True)

    def seen_ids(self) -> set[str]:
        rows = self.client.query(f"SELECT report_id FROM `{self.ds}.reports`").result()
        return {r.report_id for r in rows}

    def _load(self, table: str, rows: list[dict], cols: dict[str, str]) -> None:
        if not rows:
            return
        # Load jobs (not streaming inserts) so a reprocessed report can be deleted right away.
        cfg = bigquery.LoadJobConfig(
            schema=[bigquery.SchemaField(c, t) for c, t in cols.items()],
            write_disposition="WRITE_APPEND",
        )
        clean = [{c: r.get(c) for c in cols} for r in rows]
        self.client.load_table_from_json(clean, f"{self.ds}.{table}", job_config=cfg).result()

    def save(self, report_row: dict, figure_rows: list[dict]) -> None:
        params = [bigquery.ScalarQueryParameter("rid", "STRING", report_row["report_id"])]
        cfg = bigquery.QueryJobConfig(query_parameters=params)
        self.client.query(f"DELETE FROM `{self.ds}.figures` WHERE report_id = @rid", job_config=cfg).result()
        self.client.query(f"DELETE FROM `{self.ds}.reports` WHERE report_id = @rid", job_config=cfg).result()
        self._load("reports", [report_row], REPORT_COLUMNS)
        self._load("figures", figure_rows, FIGURE_COLUMNS)

    def reports(self) -> pd.DataFrame:
        return self.client.query(f"SELECT * FROM `{self.ds}.reports` ORDER BY published DESC").to_dataframe()

    def figures(self) -> pd.DataFrame:
        return self.client.query(
            f"SELECT * FROM `{self.ds}.figures` ORDER BY published DESC, report_id, figure_no"
        ).to_dataframe()
