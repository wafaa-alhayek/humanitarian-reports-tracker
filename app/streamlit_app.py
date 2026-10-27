"""Live tracker: the facts pulled out of humanitarian reports, each linked to its source sentence.

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reports_tracker.config import Settings  # noqa: E402
from reports_tracker.store import get_store  # noqa: E402

st.set_page_config(page_title="Humanitarian Reports Tracker", layout="wide")


@st.cache_data(ttl=600)
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    store = get_store(Settings())
    reports, figures = store.reports(), store.figures()
    for df in (reports, figures):
        df["published"] = pd.to_datetime(df["published"])
    figures = figures.merge(reports[["report_id", "title", "url", "organizations"]], on="report_id", how="left")
    return reports, figures


reports, figures = load()

st.title("Humanitarian Reports Tracker")
st.caption("Numbers extracted by AI from public reports, each one shown with the sentence it came from. "
           "A figure is **verified** when its quoted sentence was found word for word in the report.")

if reports.empty:
    st.info("No reports yet. Run `python -m reports_tracker run --limit 10` first.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    only_verified = st.checkbox("Verified figures only", value=True)
    indicators = sorted(figures["indicator"].dropna().unique())
    chosen = st.multiselect("Indicators", indicators, default=[i for i in indicators if i != "other"])
    orgs = sorted({o for v in reports["organizations"].dropna() for o in v.split("; ") if o})
    chosen_orgs = st.multiselect("Publisher", orgs)
    text = st.text_input("Search title or evidence")
    models = sorted(reports["model"].dropna().unique())
    st.caption(f"Model(s): {', '.join(models)}")

f = figures.copy()
if only_verified:
    f = f[f["verified"]]
if chosen:
    f = f[f["indicator"].isin(chosen)]
if chosen_orgs:
    f = f[f["organizations"].fillna("").apply(lambda v: any(o in v for o in chosen_orgs))]
if text:
    mask = f["title"].str.contains(text, case=False, na=False) | f["evidence"].str.contains(text, case=False, na=False)
    f = f[mask]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Reports processed", len(reports))
c2.metric("Figures extracted", len(figures))
c3.metric("Verified", f"{figures['verified'].mean():.0%}" if len(figures) else "n/a")
c4.metric("Latest report", reports["published"].max().strftime("%d %b %Y"))

st.subheader("Most recent mention of each indicator")
latest = (f.sort_values("published").groupby(["indicator", "unit"], as_index=False).tail(1)
          .sort_values("indicator"))
cols = st.columns(4)
for i, row in enumerate(latest.itertuples()):
    with cols[i % 4]:
        st.metric(row.indicator.replace("_", " ").capitalize(), f"{row.value:,.0f} {row.unit}",
                  help=f"{row.label}\n\n“{row.evidence}”\n\n{row.title}")
        st.caption(f"{row.location or ''} · {row.published:%d %b} · [source]({row.url})")

st.subheader("Figures over time")
if not f.empty:
    chart = (
        alt.Chart(f[f["unit"].isin(["people", "households"]) & (f["value"] > 0)])
        .mark_circle(size=70, opacity=0.8)
        .encode(
            x=alt.X("published:T", title="Report date"),
            y=alt.Y("value:Q", title="Value", scale=alt.Scale(type="log")),
            color=alt.Color("indicator:N", title="Indicator"),
            tooltip=["indicator", alt.Tooltip("value:Q", format=","), "unit", "location", "label", "title"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

st.subheader("All figures")
st.dataframe(
    f[["published", "indicator", "value", "unit", "location", "as_of_date", "label", "evidence", "verified", "url"]],
    use_container_width=True, hide_index=True,
    column_config={"url": st.column_config.LinkColumn("Source"),
                   "value": st.column_config.NumberColumn(format="%,.0f"),
                   "published": st.column_config.DateColumn("Published")},
)
st.download_button("Download figures (CSV)", f.to_csv(index=False), "figures.csv", "text/csv")

st.subheader("Reports")
for r in reports.head(30).itertuples():
    with st.expander(f"{r.published:%d %b %Y} · {r.title}"):
        st.write(r.summary)
        st.caption(f"{r.organizations} · {r.report_type} · {r.n_verified}/{r.n_figures} figures verified · "
                   f"[report]({r.url})" + (f" · [PDF]({r.file_url})" if isinstance(r.file_url, str) and r.file_url.startswith("http") else ""))
