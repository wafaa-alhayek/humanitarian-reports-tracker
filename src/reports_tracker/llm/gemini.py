"""Google Gemini over its REST API (no SDK needed)."""
from __future__ import annotations

import time

import requests

from ..schema import Extraction, Report
from .base import OUTPUT_SCHEMA, build_prompt, parse_json, to_extraction

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiExtractor:
    def __init__(self, api_key: str, model: str, max_chars: int = 40000):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Get one at https://aistudio.google.com/apikey")
        self.api_key, self.model, self.max_chars = api_key, model, max_chars
        self.name = f"gemini:{model}"

    def extract(self, report: Report) -> Extraction:
        body = {
            "contents": [{"role": "user", "parts": [{"text": build_prompt(report, self.max_chars)}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": OUTPUT_SCHEMA,
            },
        }
        for attempt in range(4):
            resp = requests.post(
                URL.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},
                json=body,
                timeout=180,
            )
            if resp.status_code in (429, 500, 503) and attempt < 3:
                time.sleep(2 ** (attempt + 2))  # free tier rate limits: back off and retry
                continue
            resp.raise_for_status()
            break
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return to_extraction(parse_json("".join(p.get("text", "") for p in parts)))
