import json
from datetime import datetime, timezone

import pytest
import httpx
from langchain_core.tools import tool

from config import Settings
from schemas import (BestTimeToVisit, CityCandidate, CityReport, CityResearchBundle,
                     DiscoveryExtraction, LocalTransportation, PlaceToVisit, SearchResult)


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    original = httpx.HTTPTransport.handle_request

    def guarded(self, request):
        if request.url.host in {"127.0.0.1", "localhost"}:
            return original(self, request)
        raise AssertionError("Tests must not make external HTTP requests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", guarded)


@pytest.fixture
def settings():
    return Settings(youcom_api_key="test-only", places_per_city=1, max_retries=0)


@pytest.fixture
def population_result():
    return SearchResult(title="Test national urban census", url="https://statistics.example/ranking",
        snippet="2024 urban census national ranking: Alpha 3000000; Beta 2000000; Gamma 1000000. These are the three largest urban areas.",
        publisher="Test Statistics", published_at=None, accessed_at=datetime.now(timezone.utc))


@pytest.fixture
def cities(population_result):
    return [CityCandidate(city_name=name, metro_or_urban_area_name=f"{name} Urban Area", country="Japan",
            population=population, population_year=2024, population_definition="Census urban area",
            source_urls=[population_result.url], confidence="high", notes=None)
            for name, population in (("Alpha", 3000000), ("Beta", 2000000), ("Gamma", 1000000))]


@pytest.fixture
def discovery(cities):
    return DiscoveryExtraction(cities=list(reversed(cities)), dataset_name="Test Census 2024",
        area_type="urban", consistent_definition=True, ranking_supported=True,
        ranking_basis="Three largest census urban areas", population_data_note="Test estimates.",
        warnings=[], limitation=None)


def bundle_for(city):
    def result(section, snippet):
        return SearchResult(title=f"{city.city_name} {section}",
            url=f"https://tourism.example/{city.city_name.lower()}/{section}", snippet=snippet,
            publisher="Test Tourism", published_at=None, accessed_at=datetime.now(timezone.utc))
    return CityResearchBundle(city_name=city.city_name, country=city.country,
        places=[result("places", f"{city.city_name} Museum displays local history and is a visitor attraction.")],
        timing=[result("timing", "April has mild weather and smaller crowds; recommended for visits.")],
        transportation=[result("transport", "The metro is the easiest visitor transport; buses are alternatives.")])


def report_for(city):
    bundle = bundle_for(city)
    return CityReport(city=city,
        important_places=[PlaceToVisit(name=f"{city.city_name} Museum", category="Museum",
            short_description="Local history displays", why_visit="Learn about local history",
            source_urls=[bundle.places[0].url])],
        best_time_to_visit=BestTimeToVisit(recommended_months=["April"], summary="Visit in April.",
            weather_considerations="Mild weather", crowd_or_price_considerations="Smaller crowds",
            source_urls=[bundle.timing[0].url]),
        getting_around=LocalTransportation(recommended_primary_mode="Metro", explanation="Easiest for visitors",
            public_transport_options=["Metro", "Bus"], alternatives=["Bus"], practical_tips=[],
            accessibility_or_safety_notes=[], source_urls=[bundle.transportation[0].url]),
        sources=[], missing_information=[], confidence="high")


class FakeLLM:
    """Mock the common structured-output boundary, recording exactly what each call saw."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.schemas = []

    def with_structured_output(self, schema, **kwargs):
        self.schemas.append(schema)
        return self

    def invoke(self, messages):
        self.calls.append(json.loads(messages[-1].content))
        return self.responses.pop(0)


@pytest.fixture
def search(population_result, cities):
    @tool
    def mocked_search(query: str, count: int = 8) -> list[dict]:
        """Return deterministic city-specific evidence."""
        city = next((c for c in cities if c.city_name in query), None)
        if city is None:
            rows = [population_result]
        else:
            bundle = bundle_for(city)
            if any(word in query for word in ("months", "climate", "season")):
                rows = bundle.timing
            elif any(word in query for word in ("around", "transportation", "rideshare")):
                rows = bundle.transportation
            else:
                rows = bundle.places
        return [r.model_dump(mode="json") for r in rows]
    return mocked_search
