"""Strict report contracts and structured extraction envelopes."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (BaseModel, ConfigDict, Field, HttpUrl, PlainSerializer,
                      WithJsonSchema, WrapValidator, model_validator)


def _exact_url(value, handler):
    # Validate through HttpUrl, but retain the service's spelling on serialization.
    validated = handler(value)
    return ExactHttpUrl(str(value) if isinstance(value, (str, HttpUrl)) else str(validated))


class ExactHttpUrl(HttpUrl):
    def __init__(self, url):
        super().__init__(url)
        self.original = str(url)

    def __str__(self):
        return self.original


CitationUrl = Annotated[HttpUrl, WrapValidator(_exact_url),
                        PlainSerializer(lambda value: str(value), return_type=str),
                        WithJsonSchema({"type": "string", "format": "uri"})]
Confidence = Literal["high", "medium", "low"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class SourceReference(StrictModel):
    title: str = Field(min_length=1)
    url: CitationUrl
    publisher: str | None
    accessed_at: datetime
    supports: list[str] = Field(min_length=1)


class CityCandidate(StrictModel):
    city_name: str = Field(min_length=1)
    metro_or_urban_area_name: str = Field(min_length=1)
    country: str = Field(min_length=1)
    population: int | None = Field(ge=1)
    population_year: int | None = Field(ge=1800, le=2100)
    population_definition: str = Field(min_length=1)
    source_urls: list[CitationUrl] = Field(min_length=1)
    confidence: Confidence
    notes: str | None

    @model_validator(mode="after")
    def population_has_year(self):
        if self.population is not None and self.population_year is None:
            raise ValueError("A population figure requires a year.")
        return self


class PlaceToVisit(StrictModel):
    name: str = Field(min_length=1)
    category: str
    short_description: str
    why_visit: str
    source_urls: list[CitationUrl] = Field(min_length=1)


class LocalTransportation(StrictModel):
    recommended_primary_mode: str
    explanation: str
    public_transport_options: list[str]
    alternatives: list[str]
    practical_tips: list[str]
    accessibility_or_safety_notes: list[str]
    source_urls: list[CitationUrl]


class BestTimeToVisit(StrictModel):
    recommended_months: list[Literal["January", "February", "March", "April", "May", "June",
                                     "July", "August", "September", "October", "November", "December"]]
    summary: str
    weather_considerations: str
    crowd_or_price_considerations: str
    source_urls: list[CitationUrl]


class CityReport(StrictModel):
    city: CityCandidate
    important_places: list[PlaceToVisit]
    best_time_to_visit: BestTimeToVisit
    getting_around: LocalTransportation
    sources: list[SourceReference]
    missing_information: list[str]
    confidence: Confidence


class CountryResearchReport(StrictModel):
    country: str
    ranking_basis: str
    population_data_note: str
    cities: list[CityReport] = Field(min_length=3, max_length=3)
    generated_at: datetime
    warnings: list[str]


class SearchResult(StrictModel):
    title: str = Field(min_length=1)
    url: CitationUrl
    snippet: str
    publisher: str | None
    published_at: str | None
    accessed_at: datetime


class CityResearchBundle(StrictModel):
    city_name: str
    country: str
    places: list[SearchResult]
    timing: list[SearchResult]
    transportation: list[SearchResult]

    def all_results(self) -> list[SearchResult]:
        return [*self.places, *self.timing, *self.transportation]


class DiscoveryExtraction(StrictModel):
    cities: list[CityCandidate] = Field(max_length=3)
    dataset_name: str
    area_type: Literal["metropolitan", "urban", "urban_agglomeration", "unavailable"]
    consistent_definition: bool
    ranking_supported: bool
    ranking_basis: str
    population_data_note: str
    warnings: list[str]
    limitation: str | None
