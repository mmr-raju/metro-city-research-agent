import json

import pytest
from pydantic import ValidationError

from schemas import CityCandidate, SearchResult


@pytest.mark.parametrize("population", ["1000000", 1.5, True, -1, 0])
def test_reject_malformed_population(cities, population):
    data = cities[0].model_dump(mode="json")
    data["population"] = population
    with pytest.raises(ValidationError):
        CityCandidate.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("url", ["not-a-url", "ftp://example.org/data", "javascript:alert(1)"])
def test_reject_invalid_url(cities, url):
    data = cities[0].model_dump(mode="json")
    data["source_urls"] = [url]
    with pytest.raises(ValidationError):
        CityCandidate.model_validate_json(json.dumps(data))


def test_population_requires_year(cities):
    data = cities[0].model_dump(mode="json")
    data["population_year"] = None
    with pytest.raises(ValidationError):
        CityCandidate.model_validate_json(json.dumps(data))


def test_extra_fields_rejected(cities):
    with pytest.raises(ValidationError):
        CityCandidate.model_validate_json(json.dumps({**cities[0].model_dump(mode="json"), "invented": True}))


@pytest.mark.parametrize("url", ["https://example.com", "https://EXAMPLE.com/a?utm_source=x#section"])
def test_exact_service_url_survives_json(population_result, url):
    data = population_result.model_dump(mode="json")
    data["url"] = url
    result = SearchResult.model_validate_json(json.dumps(data))
    assert str(result.url) == url
    assert result.model_dump(mode="json")["url"] == url
