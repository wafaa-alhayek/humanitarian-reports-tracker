"""Run the whole flow: fetch reports -> get text -> extract facts -> check them -> store.

    python -m reports_tracker run --country "occupied Palestinian territory" --limit 10
    python -m reports_tracker run --source local --folder data/inbox --llm ollama
    python -m reports_tracker export --out data/export
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings
from .llm import get_extractor
from .llm.base import is_grounded
from .schema import Figure, Report
from .sources import local, reliefweb
from .store import get_store, to_rows
from .text import clean, detect_language, download, pdf_to_text

log = logging.getLogger("reports_tracker")


def add_text(report: Report, settings: Settings) -> Report:
    """Fill report.text from its PDF, keeping any web-page text as a lead-in."""
    if report.file_url:
        try:
            data = download(report.file_url, settings.pdf_cache)
            if data:
                pdf_text = pdf_to_text(data)
                report.text = clean(f"{report.text}\n{pdf_text}") if report.text else pdf_text
        except Exception as exc:  # keep going with whatever text we have
            log.warning("Could not read PDF for %s: %s", report.title[:60], exc)
    report.language = report.language or detect_language(report.text)
    return report


def dedupe(figures: list[Figure]) -> list[Figure]:
    """Web-page text and PDF text often repeat the same sentence; keep one copy."""
    seen, out = set(), []
    for f in figures:
        key = (f.indicator, f.value, f.unit, (f.location or "").lower())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def run(args: argparse.Namespace, settings: Settings) -> int:
    store = get_store(settings, args.store)
    extractor = get_extractor(settings, args.llm)
    seen = set() if args.reprocess else store.seen_ids()

    if args.source == "reliefweb":
        reports = reliefweb.fetch(args.country, args.query, args.limit, settings.reliefweb_appname)
    else:
        reports = local.fetch(args.folder, args.limit)

    done = failed = skipped = 0
    for report in reports:
        if report.report_id in seen:
            skipped += 1
            continue
        report = add_text(report, settings)
        if len(report.text) < 200:
            log.info("Skipping (too little text, probably an image-only PDF): %s", report.title[:80])
            skipped += 1
            continue
        try:
            ex = extractor.extract(report)
        except Exception as exc:
            log.error("Extraction failed for %s: %s", report.title[:80], exc)
            failed += 1
            continue
        ex.figures = dedupe(ex.figures)
        verified = [is_grounded(f.evidence, f.value, report.text) for f in ex.figures]
        store.save(*to_rows(report, ex, extractor.name, verified))
        done += 1
        log.info("%-70s %2d figures, %2d verified", report.title[:70], len(ex.figures), sum(verified))

    log.info("Processed %d, skipped %d, failed %d (model %s)", done, skipped, failed, extractor.name)
    return 1 if failed and not done else 0


def export(args: argparse.Namespace, settings: Settings) -> int:
    store = get_store(settings, args.store)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    store.reports().to_csv(out / "reports.csv", index=False)
    store.figures().to_csv(out / "figures.csv", index=False)
    log.info("Wrote %s and %s", out / "reports.csv", out / "figures.csv")
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = Settings()
    parser = argparse.ArgumentParser(prog="reports_tracker", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="fetch and process new reports")
    p_run.add_argument("--source", choices=["reliefweb", "local"], default="reliefweb")
    p_run.add_argument("--country", default="occupied Palestinian territory",
                       help="ReliefWeb country name; empty string for all countries")
    p_run.add_argument("--query", default=None, help='extra ReliefWeb search, e.g. "Gaza AND food"')
    p_run.add_argument("--folder", default="data/inbox", help="folder of PDFs for --source local")
    p_run.add_argument("--limit", type=int, default=10)
    p_run.add_argument("--llm", choices=["gemini", "ollama", "rules"], default=None)
    p_run.add_argument("--store", choices=["duckdb", "bigquery"], default=None)
    p_run.add_argument("--reprocess", action="store_true", help="redo reports already stored")

    p_exp = sub.add_parser("export", help="write the stored tables to CSV")
    p_exp.add_argument("--store", choices=["duckdb", "bigquery"], default=None)
    p_exp.add_argument("--out", default="data/export")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # noisy font warnings
    if getattr(args, "country", None) == "":
        args.country = None
    return {"run": run, "export": export}[args.cmd](args, settings)


if __name__ == "__main__":
    sys.exit(main())
