import pytest

from errors import EvidenceError
from evidence import audit_report
from nodes.analyst import analyst_node
from schemas import CityResearchBundle
from conftest import FakeLLM, bundle_for, report_for


def test_missing_evidence_is_reported(cities, population_result, settings):
    city = cities[0]
    bundle = CityResearchBundle(city_name=city.city_name, country=city.country,
                                 places=[], timing=[], transportation=[])
    llm = FakeLLM([])
    result = analyst_node({"current_city": city, "current_city_raw_data": bundle,
                           "discovery_results": [population_result]}, llm=llm,
                          settings=settings, progress=lambda _: None)
    report = result["city_reports"][0]
    assert report.missing_information
    assert report.confidence == "low"
    assert report.important_places == []
    assert llm.calls == []


def test_other_city_cannot_replace_current(cities, population_result):
    with pytest.raises(EvidenceError, match="identity"):
        audit_report(report_for(cities[1]), cities[0], bundle_for(cities[0]), [population_result])


def test_cross_city_citation_rejected(cities, population_result):
    report = report_for(cities[0])
    wrong = report.important_places[0].model_copy(update={"source_urls": [bundle_for(cities[1]).places[0].url]})
    report = report.model_copy(update={"important_places": [wrong]})
    with pytest.raises(EvidenceError, match="citation"):
        audit_report(report, cities[0], bundle_for(cities[0]), [population_result])


def test_unsourced_seasonal_claim_is_removed(cities, population_result):
    report = report_for(cities[0])
    timing = report.best_time_to_visit.model_copy(update={"source_urls": []})
    report = audit_report(report.model_copy(update={"best_time_to_visit": timing}), cities[0],
                          bundle_for(cities[0]), [population_result])
    assert report.best_time_to_visit.recommended_months == []
    assert "Data not found" in report.best_time_to_visit.summary
    assert report.missing_information
