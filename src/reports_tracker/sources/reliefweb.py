"""Fetch recent reports from ReliefWeb.

Two ways in:
- RSS feed (default). Public, no sign-up, latest 20 items per query.
- JSON API v2. Needs an approved appname (free, request at
  https://apidoc.reliefweb.int/parameters#appname) but allows paging and filters.
"""
from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Iterator, Optional
from urllib.parse import quote

import requests

from ..schema import Report

RSS_URL = "https://reliefweb.int/updates/rss.xml"
API_URL = "https://api.reliefweb.int/v2/reports"
HEADERS = {"User-Agent": "describe-reports-tracker/0.1 (+https://github.com/wafaa-alhayek)"}


def report_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def strip_html(raw: str) -> str:
    text = re.sub(r"<(br|/p|/div|/li|/h\d)[^>]*>", "\n", raw or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def build_search(country: Optional[str], query: Optional[str]) -> str:
    parts = []
    if country:
        parts.append(f'country.exact:"{country}"')
    if query:
        parts.append(f"({query})")
    return " AND ".join(parts)


def fetch_rss(country: Optional[str] = None, query: Optional[str] = None, limit: int = 20) -> Iterator[Report]:
    search = build_search(country, query)
    url = RSS_URL + (f"?search={quote(search)}" if search else "")
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    for item in root.findall(".//item")[:limit]:
        link = (item.findtext("link") or "").strip()
        desc_html = item.findtext("description") or ""
        # The description starts with "Country: ..." and "Source: ..." tags; keep the prose.
        desc = strip_html(re.sub(r'<div class="tag[^"]*">.*?</div>', "", desc_html, flags=re.S))
        orgs = [a.text.strip() for a in item.findall("author") if a.text]
        cats = [c.text.strip() for c in item.findall("category") if c.text]
        pdf = next(
            (e.get("url") for e in item.findall("enclosure") if (e.get("type") or "").endswith("pdf")),
            None,
        )
        published = None
        if item.findtext("pubDate"):
            published = parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
        countries = re.findall(r'class="tag country">Countr(?:y|ies): ([^<]+)<', desc_html)
        country_list = [c.strip() for c in countries[0].split(",")] if countries else []
        yield Report(
            report_id=report_id(link),
            source="reliefweb",
            url=link,
            title=(item.findtext("title") or "").strip(),
            published=published,
            organizations=orgs,
            countries=country_list,
            themes=[c for c in cats if c not in orgs and c not in country_list],
            file_url=pdf,
            text=desc,
        )


def fetch_api(appname: str, country: Optional[str] = None, query: Optional[str] = None,
              limit: int = 20) -> Iterator[Report]:
    payload: dict = {
        "limit": min(limit, 1000),
        "sort": ["date.created:desc"],
        "fields": {"include": ["title", "url_alias", "url", "date.created", "source.name",
                               "country.name", "theme.name", "file.url", "file.mimetype",
                               "body", "language.code"]},
    }
    if country:
        payload["filter"] = {"field": "country.name", "value": country}
    if query:
        payload["query"] = {"value": query}
    resp = requests.post(f"{API_URL}?appname={quote(appname)}", json=payload, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    for row in resp.json().get("data", []):
        f = row.get("fields", {})
        link = f.get("url_alias") or f.get("url") or ""
        pdf = next((x["url"] for x in f.get("file", []) if x.get("mimetype", "").endswith("pdf")), None)
        langs = [x.get("code") for x in f.get("language", [])]
        yield Report(
            report_id=report_id(link),
            source="reliefweb",
            url=link,
            title=f.get("title", ""),
            published=(f.get("date", {}).get("created") or "")[:10] or None,
            organizations=[s["name"] for s in f.get("source", [])],
            countries=[c["name"] for c in f.get("country", [])],
            themes=[t["name"] for t in f.get("theme", [])],
            file_url=pdf,
            language=langs[0] if langs else None,
            text=strip_html(f.get("body", "")),
        )


def fetch(country: Optional[str] = None, query: Optional[str] = None, limit: int = 20,
          appname: str = "") -> Iterator[Report]:
    if appname:
        return fetch_api(appname, country, query, limit)
    return fetch_rss(country, query, limit)
