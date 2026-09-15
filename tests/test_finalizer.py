import pytest

from errors import EvidenceError
from evidence import city_key
from nodes.finalizer import finalizer_node
from conftest import bundle_for, report_for


def final_state(cities, population_result):
    return {"city_reports": [report_for(c) for c in reversed(cities)], "discovered_cities": cities,
            "city_queue": [], "current_city": None, "normalized_country": "Japan",
            "discovery_results": [population_result], "evidence_by_city": {city_key(c): bundle_for(c) for c in cities},
            "ranking_basis": "Urban census", "population_data_note": "Test data", "warnings": ["Test warning", "Test warning"]}


def test_finalizer_sorts_audits_and_deduplicates(cities, population_result):
    report = finalizer_node(final_state(cities, population_result), progress=lambda _: None)["final_report"]
    assert [r.city for r in report.cities] == cities
    assert report.warnings == ["Test warning"]
    assert report.cities[0].sources[0].accessed_at == population_result.accessed_at


def test_finalizer_rejects_incomplete_run(cities, population_result):
    state = final_state(cities, population_result)
    state["city_reports"] = state["city_reports"][:2]
    with pytest.raises(EvidenceError, match="exactly three"):
        finalizer_node(state, progress=lambda _: None)


def test_finalizer_rechecks_cross_city_citations(cities, population_result):
    state = final_state(cities, population_result)
    original = state["city_reports"][0]
    bad_transport = original.getting_around.model_copy(update={
        "source_urls": [bundle_for(cities[0]).transportation[0].url]})
    state["city_reports"] = [original.model_copy(update={"getting_around": bad_transport}), *state["city_reports"][1:]]
    with pytest.raises(EvidenceError, match="citation"):
        finalizer_node(state, progress=lambda _: None)
