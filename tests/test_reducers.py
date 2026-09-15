from graph import build_graph
from state import initial_state
from conftest import FakeLLM, report_for


def test_full_graph_accumulates_and_isolates_three_reports(discovery, cities, search, settings):
    llm = FakeLLM([discovery, *[report_for(city) for city in cities]])
    events = []
    workflow = build_graph(llm, search, settings, events.append)
    result = workflow.invoke(initial_state("Japan"))
    assert [r.city.city_name for r in result["city_reports"]] == ["Alpha", "Beta", "Gamma"]
    assert [r.city.city_name for r in result["final_report"].cities] == ["Alpha", "Beta", "Gamma"]
    assert len([e for e in events if e.startswith("Discovery:")]) == 1
    assert result["current_city"] is None
    assert result["current_city_raw_data"] is None
    assert result["city_queue"] == []
    assert len(llm.calls) == 4
    for call, city in zip(llm.calls[1:], cities):
        assert call["current_city"]["city_name"] == city.city_name
        assert call["evidence"]["city_name"] == city.city_name
        assert "city_reports" not in call
        for other in cities:
            if other != city:
                assert other.city_name not in str(call)


def test_stream_routes_exactly_one_city_per_iteration(discovery, cities, search, settings):
    graph = build_graph(FakeLLM([discovery, *map(report_for, cities)]), search, settings)
    updates = list(graph.stream(initial_state("Japan"), stream_mode="updates"))
    assert [next(iter(event)) for event in updates] == [
        "discovery", "researcher", "analyst", "researcher", "analyst", "researcher", "analyst", "finalizer"]
    assert all(len(event["analyst"]["city_reports"]) == 1 for event in updates if "analyst" in event)
