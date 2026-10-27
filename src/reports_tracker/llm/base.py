"""The extraction prompt, the output schema, and checks that every backend shares."""
from __future__ import annotations

import json
import re
from typing import Protocol

from ..schema import INDICATORS, Extraction, Report

PROMPT = """You are a humanitarian data analyst. Read the report below and extract structured facts.

Rules:
- Only use numbers that are written in the report. Never estimate, add up or infer numbers.
- For each number, copy the exact sentence or phrase that contains it into "evidence",
  in the report's original language (Arabic stays Arabic).
- Pick the closest indicator from this list, else "other": {indicators}.
- "value" is a plain number: 1.9 million -> 1900000, 45% -> 45 with unit "percent".
- Funding amounts go in USD with unit "USD".
- Prefer the most specific location named (camp, city, governorate) over the country.
- Skip numbers that are only dates, page numbers, phone numbers or list numbering.
- Return at most {max_figures} figures, the most important first.
- The summary is always in English, even when the report is in Arabic.

Report title: {title}
Published: {published}
Publisher: {orgs}

Report text:
\"\"\"
{text}
\"\"\"
"""

# Plain schema understood by both Gemini (responseSchema) and Ollama (format).
OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "report_type": {"type": "string"},
        "locations": {"type": "array", "items": {"type": "string"}},
        "sectors": {"type": "array", "items": {"type": "string"}},
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indicator": {"type": "string", "enum": INDICATORS},
                    "value": {"type": "number"},
                    "unit": {"type": "string"},
                    "location": {"type": "string"},
                    "as_of_date": {"type": "string"},
                    "label": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["indicator", "value", "unit", "label", "evidence"],
            },
        },
    },
    "required": ["summary", "report_type", "locations", "sectors", "figures"],
}


class Extractor(Protocol):
    name: str

    def extract(self, report: Report) -> Extraction: ...


def build_prompt(report: Report, max_chars: int, max_figures: int = 25) -> str:
    return PROMPT.format(
        indicators=", ".join(INDICATORS),
        max_figures=max_figures,
        title=report.title,
        published=report.published or "unknown",
        orgs=", ".join(report.organizations) or "unknown",
        text=report.text[:max_chars],
    )


def parse_json(raw: str) -> dict:
    """Models sometimes wrap JSON in ``` fences or add a sentence; take the object."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


def to_extraction(data: dict) -> Extraction:
    figures = []
    for f in data.get("figures") or []:
        if not isinstance(f, dict):
            continue
        if f.get("indicator") not in INDICATORS:
            f["indicator"] = "other"
        for key in ("location", "as_of_date"):
            if f.get(key) in ("", "null", "None", "unknown"):
                f[key] = None
        figures.append(f)
    data["figures"] = figures
    return Extraction.model_validate(data)


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_ARABIC_DIGITS)).strip().lower()


def is_grounded(evidence: str, value: float, text: str) -> bool:
    """True when the quoted evidence really appears in the report and holds a number.

    This is the guard against a model inventing figures: anything it cannot
    point to in the source text is flagged as unverified in the tracker.
    """
    ev, body = _norm(evidence), _norm(text)
    if not ev or not re.search(r"\d", ev):
        return False
    if ev in body:
        return True
    # PDF text often breaks lines or hyphenates differently; accept if most of the
    # evidence's words appear in order within a short window of the text.
    words = re.findall(r"\w+", ev)
    if len(words) < 3:
        return False
    first = body.find(words[0])
    while first != -1:
        window = body[first:first + len(ev) * 2]
        pos, hits = 0, 0
        for w in words:
            nxt = window.find(w, pos)
            if nxt != -1:
                hits, pos = hits + 1, nxt + len(w)
        if hits / len(words) >= 0.85:
            return True
        first = body.find(words[0], first + 1)
    return False
