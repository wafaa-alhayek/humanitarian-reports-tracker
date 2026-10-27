"""Data model shared by every step: what a report is, and which facts we pull out of it."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# A fixed list keeps the tracker comparable across reports and models.
# "other" catches anything useful that does not fit.
Indicator = Literal[
    "people_killed",
    "people_injured",
    "people_displaced",
    "people_in_need",
    "people_reached",
    "food_insecure",
    "children_affected",
    "health_facilities_affected",
    "schools_affected",
    "homes_damaged_or_destroyed",
    "aid_trucks_entered",
    "funding_required_usd",
    "funding_received_usd",
    "other",
]

INDICATORS: list[str] = list(Indicator.__args__)  # type: ignore[attr-defined]


class Report(BaseModel):
    """One document as it came from a source, before any AI step."""

    report_id: str                      # stable id, e.g. a hash of the URL
    source: str                         # "reliefweb", "local", ...
    url: str
    title: str
    published: Optional[str] = None     # ISO date
    organizations: list[str] = []
    countries: list[str] = []
    themes: list[str] = []
    file_url: Optional[str] = None      # the PDF, when there is one
    language: Optional[str] = None
    text: str = ""                      # full extracted text


class Figure(BaseModel):
    """One number stated in a report, with the sentence that backs it."""

    indicator: Indicator
    value: float
    unit: str = Field("people", description="people, households, facilities, trucks, USD, percent, ...")
    location: Optional[str] = Field(None, description="Most specific place named, e.g. 'Gaza Strip', 'Khan Younis'")
    as_of_date: Optional[str] = Field(None, description="Date or period the number refers to, ISO if possible")
    label: str = Field(..., description="Short plain-English description of the number")
    evidence: str = Field(..., description="Exact sentence or phrase from the report containing the number")


class Extraction(BaseModel):
    """What the language model returns for one report."""

    summary: str = Field(..., description="Two or three sentence English summary")
    report_type: str = Field("other", description="situation report, flash update, assessment, infographic, appeal, press release, other")
    locations: list[str] = []
    sectors: list[str] = Field([], description="e.g. health, food security, shelter, WASH, protection, education")
    figures: list[Figure] = []
