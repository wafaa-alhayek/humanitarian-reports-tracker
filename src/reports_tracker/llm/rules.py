"""A no-AI baseline: keyword patterns around numbers.

Useful for testing the pipeline without an API key, and as a benchmark that shows
how much the language model adds.
"""
from __future__ import annotations

import re

from ..schema import Extraction, Figure, Report

NUMBER = r"(\d{1,3}(?:[,\u202f]\d{3})+|\d+(?:\.\d+)?)\s*(million|thousand)?"

PATTERNS: list[tuple[str, str, str]] = [
    ("people_killed", r"(killed|deaths|fatalities|died)", "people"),
    ("people_injured", r"(injured|wounded|injuries)", "people"),
    ("people_displaced", r"(displaced|displacement|evacuat)", "people"),
    ("people_in_need", r"(in need)", "people"),
    ("people_reached", r"(reached|assisted|received assistance|benefit)", "people"),
    ("food_insecure", r"(food insecur|famine|IPC Phase)", "people"),
    ("children_affected", r"(children)", "people"),
    ("aid_trucks_entered", r"(trucks?)", "trucks"),
    ("homes_damaged_or_destroyed", r"(homes|housing units|shelters?) .{0,30}(damaged|destroyed)", "homes"),
]


def _value(num: str, scale: str | None) -> float:
    v = float(re.sub(r"[,\u202f]", "", num))
    return v * {"million": 1e6, "thousand": 1e3}.get((scale or "").lower(), 1)


MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"


def _is_date(m: re.Match, sent: str) -> bool:
    """Skip years and day numbers like '10 October' or 'October 10'."""
    if 1900 <= _value(*m.groups()) <= 2100 and not m.group(2):
        return True
    after, before = sent[m.end():m.end() + 12], sent[max(0, m.start() - 12):m.start()]
    return bool(re.match(r"\s*" + MONTHS, after, re.I) or re.search(MONTHS + r"\s*$", before, re.I))


class RulesExtractor:
    name = "rules"

    def __init__(self, max_figures: int = 25):
        self.max_figures = max_figures

    def extract(self, report: Report) -> Extraction:
        sentences = re.split(r"(?<=[.!?\n])\s+", report.text)
        figures: list[Figure] = []
        for sent in sentences:
            if len(figures) >= self.max_figures:
                break
            numbers = [m for m in re.finditer(NUMBER, sent, re.I) if not _is_date(m, sent)]
            for indicator, keywords, unit in PATTERNS:
                m_kw = re.search(keywords, sent, re.I)
                if not (m_kw and numbers):
                    continue
                # Numbers usually come just before their keyword ("42 people were killed").
                m_num = min(numbers, key=lambda m: m_kw.start() - m.start() if m.start() < m_kw.start()
                            else 40 + m.start() - m_kw.start())
                value = _value(*m_num.groups())
                figures.append(Figure(indicator=indicator, value=value, unit=unit,
                                      label=f"{indicator.replace('_', ' ')} (pattern match)",
                                      evidence=sent.strip()[:400]))
        first = " ".join(s.strip() for s in sentences[:2])[:400]
        return Extraction(summary=first or report.title, report_type="other",
                          locations=report.countries, sectors=report.themes, figures=figures)
