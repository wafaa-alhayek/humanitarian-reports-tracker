# Humanitarian Reports Tracker

Turns humanitarian PDF reports into a clean, searchable table of facts, and shows them in a live tracker.

Every day, UN agencies and NGOs publish dozens of situation reports, flash updates and infographics on [ReliefWeb](https://reliefweb.int). The numbers inside them (people displaced, people killed, aid trucks entered, funding received) are locked in PDFs. This project reads those PDFs with an AI model, pulls out each number together with the exact sentence it came from, checks that the sentence really exists in the report, and stores the result in DuckDB or BigQuery.

Built by [Describe](https://github.com/wafaa-alhayek), a data agency in Gaza.

## How it works

```
ReliefWeb (RSS or API)  ──►  download PDF  ──►  PDF to text  ──►  AI extraction  ──►  evidence check  ──►  DuckDB / BigQuery  ──►  Streamlit tracker
      or a local folder                                         Gemini | local Ollama
                                                                | rules (no AI)
```

1. **Fetch.** New reports for a country (default: occupied Palestinian territory) come from ReliefWeb's public RSS feed. With a free ReliefWeb API "appname" it uses the JSON API instead. You can also drop your own PDFs in a folder.
2. **Read.** Attached PDFs are downloaded (and cached) and converted to text.
3. **Extract.** A language model returns a summary, report type, places, sectors, and a list of figures. Each figure has an indicator from a fixed list (`people_displaced`, `people_killed`, `aid_trucks_entered`, `funding_required_usd`, ...), a value, unit, place, date, and the **evidence**: the sentence copied from the report.
4. **Verify.** Each evidence sentence is searched for in the report text (Arabic digits and PDF line breaks are handled). Figures whose sentence cannot be found are kept but marked **unverified**, so an invented number never shows up as fact.
5. **Store.** Two tables, `reports` and `figures`, in a local DuckDB file or in BigQuery. Reports already processed are skipped on the next run.
6. **Show.** A Streamlit tracker lists the latest figures, a timeline, a searchable table with source links, and report summaries.

### Choosing the model

| Backend | Where text goes | Needs | Good for |
|---|---|---|---|
| `gemini` | Google's Gemini API | `GEMINI_API_KEY` ([free key](https://aistudio.google.com/apikey)) | Best quality, long reports, Arabic |
| `ollama` | Stays on your computer | [Ollama](https://ollama.com) + a model, e.g. `ollama pull qwen2.5:7b` | Sensitive documents, no internet, no cost |
| `rules` | Stays on your computer | Nothing | Testing, and as a baseline that shows what the AI adds |

Switch with `--llm` or `LLM_BACKEND` in `.env`. All three return the same structure, so the tables and the tracker work the same.

## Quick start

```bash
pip install -e ".[app,dev]"          # add ,bigquery for BigQuery
cp .env.example .env                 # then paste your GEMINI_API_KEY

# 10 latest reports on the occupied Palestinian territory, with Gemini, into data/reports.duckdb
python -m reports_tracker run --limit 10

# no API key yet? try the offline baseline
python -m reports_tracker run --limit 10 --llm rules

# open the tracker
streamlit run app/streamlit_app.py
```

More options:

```bash
python -m reports_tracker run --country "Sudan" --limit 20
python -m reports_tracker run --query "Gaza AND food" --limit 20
python -m reports_tracker run --country "" --limit 20           # all countries
python -m reports_tracker run --source local --folder data/inbox --llm ollama
python -m reports_tracker run --reprocess --llm gemini         # redo stored reports, e.g. after switching model
python -m reports_tracker export --out data/export             # CSVs of both tables
```

## BigQuery and daily automation

```bash
gcloud auth application-default login
python -m reports_tracker run --store bigquery     # with BQ_PROJECT set in .env
```

The dataset (`humanitarian_reports` by default) and tables are created on the first run. `figures` is partitioned by publication date. Point the tracker at BigQuery by setting `STORE=bigquery`, or connect Looker Studio straight to the tables.

`.github/workflows/daily-run.yml` runs the pipeline every morning at 08:00 Gaza time on GitHub Actions. Add these repository secrets to switch it on: `GEMINI_API_KEY`, `GCP_SA_KEY` (a service account JSON key with BigQuery Data Editor and Job User roles), `BQ_PROJECT`, and optionally `RELIEFWEB_APPNAME`.

## Tables

**reports**: `report_id, source, url, title, published, organizations, countries, themes, file_url, language, n_chars, summary, report_type, locations, sectors, model, n_figures, n_verified, processed_at`

**figures**: `report_id, figure_no, indicator, value, unit, location, as_of_date, label, evidence, verified, model, published`

## Limits to know

- Image-only PDFs (scanned pages, some infographics) have no text layer and are skipped. Gemini can read PDFs as images; adding that is on the list below.
- Reports often repeat earlier cumulative totals. The tracker shows what each report says, it does not yet reconcile one official series per indicator.
- The `rules` backend is a crude keyword matcher. Its figures are "verified" because it copies whole sentences, but its labels and values are often wrong. That gap is the point of comparing it to the AI.
- ReliefWeb's RSS returns the 20 newest items per query. For history or larger pulls, request an API appname.

## Roadmap

- [ ] Send image-only PDFs to Gemini as files
- [ ] Compare Gemini and a local model on a hand-checked set of 30 reports (precision of figures)
- [ ] HDX datasets and OCHA Arabic reports as extra sources
- [ ] One deduplicated time series per indicator and place
- [ ] Alerts when a figure jumps (for example a sharp rise in displacement)

## Tests

```bash
pytest -q
```

Tests cover the evidence check (including Arabic digits), the Gemini and Ollama request formats (with mocked HTTP), the rules baseline, and a full run from a local folder into DuckDB.
