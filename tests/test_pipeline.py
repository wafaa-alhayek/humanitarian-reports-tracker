import shutil

import duckdb

from reports_tracker.pipeline import main


def test_local_folder_end_to_end(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    shutil.copy("tests/fixtures/flash_update.txt", inbox)
    db = tmp_path / "r.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(db))

    assert main(["run", "--source", "local", "--folder", str(inbox), "--llm", "rules", "--store", "duckdb"]) == 0
    con = duckdb.connect(str(db))
    assert con.execute("SELECT count(*) FROM reports").fetchone()[0] == 1
    n_figures = con.execute("SELECT count(*) FROM figures").fetchone()[0]
    assert n_figures >= 3
    assert con.execute("SELECT bool_and(verified) FROM figures").fetchone()[0]
    con.close()

    # A second run skips what is already stored; --reprocess replaces it without duplicates.
    assert main(["run", "--source", "local", "--folder", str(inbox), "--llm", "rules"]) == 0
    assert main(["run", "--source", "local", "--folder", str(inbox), "--llm", "rules", "--reprocess"]) == 0
    con = duckdb.connect(str(db))
    assert con.execute("SELECT count(*) FROM reports").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM figures").fetchone()[0] == n_figures
    con.close()

    out = tmp_path / "export"
    assert main(["export", "--out", str(out)]) == 0
    assert (out / "figures.csv").exists()
