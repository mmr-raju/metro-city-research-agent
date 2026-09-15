from datetime import datetime, timezone

from errors import EvidenceError
from evidence import audit_report, city_key
from nodes.common import Progress
from schemas import CountryResearchReport
from state import ResearchState


def finalizer_node(state: ResearchState, *, progress: Progress) -> dict:
    progress("Finalizing: verifying three reports and their citation boundaries")
    reports = state.get("city_reports", [])
    discovered = state.get("discovered_cities", [])
    if (len(reports) != 3 or len(discovered) != 3 or state["city_queue"]
            or state.get("current_city") is not None):
        raise EvidenceError("Research did not complete exactly three city reports. Retry research.")
    lookup = {city_key(report.city): report for report in reports}
    if len(lookup) != 3 or set(lookup) != {city_key(city) for city in discovered}:
        raise EvidenceError("The completed cities differ from the discovery ranking. Retry research.")
    ordered = []
    for city in sorted(discovered, key=lambda c: c.population or 0, reverse=True):
        bundle = state.get("evidence_by_city", {}).get(city_key(city))
        if bundle is None:
            raise EvidenceError("A city's retrieval audit trail is missing. Retry research.")
        ordered.append(audit_report(lookup[city_key(city)], city, bundle, state["discovery_results"]))
    warnings = list(dict.fromkeys(state.get("warnings", [])))
    if any(r.missing_information for r in ordered):
        warnings.append("Some travel details are unavailable; review each city's missing-information section.")
    warnings = list(dict.fromkeys(warnings))
    note = " ".join([state["population_data_note"], *[w for w in warnings
                       if "different years" in w or "fallback" in w]])
    report = CountryResearchReport(country=state["normalized_country"],
        ranking_basis=state["ranking_basis"], population_data_note=note, cities=ordered,
        generated_at=datetime.now(timezone.utc), warnings=warnings)
    return {"final_report": report}
