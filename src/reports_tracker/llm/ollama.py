"""A local open-source model through Ollama, so report text never leaves the machine."""
from __future__ import annotations

import requests

from ..schema import Extraction, Report
from .base import OUTPUT_SCHEMA, build_prompt, parse_json, to_extraction


class OllamaExtractor:
    def __init__(self, url: str, model: str, max_chars: int = 12000):
        self.url, self.model = url.rstrip("/"), model
        # Small local models have small context windows; send less text.
        self.max_chars = min(max_chars, 12000)
        self.name = f"ollama:{model}"

    def extract(self, report: Report) -> Extraction:
        resp = requests.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": build_prompt(report, self.max_chars, max_figures=15)}],
                "format": OUTPUT_SCHEMA,  # Ollama >= 0.5 constrains output to this schema
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 16384},
            },
            timeout=600,
        )
        resp.raise_for_status()
        return to_extraction(parse_json(resp.json()["message"]["content"]))
