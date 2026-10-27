import json

import pytest

from reports_tracker.llm.base import OUTPUT_SCHEMA, is_grounded, parse_json, to_extraction
from reports_tracker.llm.gemini import GeminiExtractor
from reports_tracker.llm.ollama import OllamaExtractor
from reports_tracker.llm.rules import RulesExtractor
from reports_tracker.schema import Report

TEXT = open("tests/fixtures/flash_update.txt").read()
ARABIC = open("tests/fixtures/arabic_update.txt").read()

MODEL_OUTPUT = {
    "summary": "Displacement and casualties continued in Khan Younis.",
    "report_type": "flash update",
    "locations": ["Khan Younis", "Al Mawasi"],
    "sectors": ["protection", "food security"],
    "figures": [
        {"indicator": "people_displaced", "value": 1250, "unit": "people", "location": "Khan Younis",
         "as_of_date": "2026-10-10", "label": "People displaced from eastern Khan Younis",
         "evidence": "at least 1,250 people have been displaced from eastern Khan Younis to Al Mawasi"},
        {"indicator": "made_up_indicator", "value": 99, "unit": "people", "location": "",
         "label": "Invented", "evidence": "99 people were evacuated by helicopter"},
    ],
}


def report(text=TEXT):
    return Report(report_id="r1", source="test", url="https://example.org/r1", title="Update", text=text)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_grounding_accepts_real_quote_and_rejects_invented_one():
    assert is_grounded("42 people were killed and 118 injured", 42, TEXT)
    assert not is_grounded("99 people were evacuated by helicopter", 99, TEXT)
    assert not is_grounded("no number here", 0, TEXT)


def test_grounding_tolerates_pdf_line_breaks_and_arabic_digits():
    assert is_grounded("A total of 1,040 aid\ntrucks entered the Gaza Strip", 1040, TEXT)
    assert is_grounded("نزح ما لا يقل عن 3٬500 شخص", 3500, ARABIC)


def test_parse_json_handles_code_fences():
    assert parse_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_unknown_indicator_becomes_other_and_blank_location_none():
    ex = to_extraction(json.loads(json.dumps(MODEL_OUTPUT)))
    assert ex.figures[1].indicator == "other"
    assert ex.figures[1].location is None


def test_gemini_request_and_parsing(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": __import__("json").dumps(MODEL_OUTPUT)}]}}]})

    monkeypatch.setattr("reports_tracker.llm.gemini.requests.post", fake_post)
    ex = GeminiExtractor("key", "gemini-2.5-flash").extract(report())
    assert "gemini-2.5-flash:generateContent" in sent["url"]
    assert sent["headers"]["x-goog-api-key"] == "key"
    assert sent["body"]["generationConfig"]["responseSchema"] == OUTPUT_SCHEMA
    assert ex.figures[0].value == 1250


def test_gemini_needs_key():
    with pytest.raises(ValueError):
        GeminiExtractor("", "gemini-2.5-flash")


def test_ollama_request_and_parsing(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, body=json)
        return FakeResponse({"message": {"content": __import__("json").dumps(MODEL_OUTPUT)}})

    monkeypatch.setattr("reports_tracker.llm.ollama.requests.post", fake_post)
    ex = OllamaExtractor("http://localhost:11434/", "qwen2.5:7b").extract(report())
    assert sent["url"] == "http://localhost:11434/api/chat"
    assert sent["body"]["format"] == OUTPUT_SCHEMA
    assert ex.locations == ["Khan Younis", "Al Mawasi"]


def test_rules_baseline_finds_core_numbers():
    ex = RulesExtractor().extract(report())
    found = {(f.indicator, f.value) for f in ex.figures}
    assert ("people_displaced", 1250) in found
    assert ("people_killed", 42) in found
    assert ("aid_trucks_entered", 1040) in found
