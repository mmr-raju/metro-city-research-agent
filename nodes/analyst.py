from langchain_core.language_models import BaseChatModel

from config import Settings
from errors import EvidenceError
from evidence import MISSING, audit_report
from nodes.common import Progress, extract
from prompts import ANALYST_PROMPT
from schemas import BestTimeToVisit, CityReport, LocalTransportation
from state import ResearchState


def analyst_node(state: ResearchState, *, llm: BaseChatModel, settings: Settings,
                 progress: Progress) -> dict:
    city = state.get("current_city")
    bundle = state.get("current_city_raw_data")
    if city is None or bundle is None:
        raise EvidenceError("Current-city evidence is missing. Restart research.")
    progress(f"Analyzing {city.city_name}: checking recommendations and citations")
    if not any(r.snippet.strip() for r in bundle.all_results()):
        report = CityReport(city=city, important_places=[],
                            best_time_to_visit=BestTimeToVisit(recommended_months=[], summary=MISSING,
                                weather_considerations=MISSING, crowd_or_price_considerations=MISSING, source_urls=[]),
                            getting_around=LocalTransportation(recommended_primary_mode=MISSING,
                                explanation=MISSING, public_transport_options=[], alternatives=[], practical_tips=[],
                                accessibility_or_safety_notes=[], source_urls=[]),
                            sources=[], missing_information=[MISSING], confidence="low")
    else:
        report = extract(llm, CityReport, ANALYST_PROMPT,
                         {"current_city": city.model_dump(mode="json"),
                          "evidence": bundle.model_dump(mode="json"),
                          "places_per_city": settings.places_per_city})
    report = audit_report(report, city, bundle, state["discovery_results"])
    places = report.important_places[:settings.places_per_city]
    # Prevent duplicate names from counting toward the desired number of places.
    unique = {place.name.casefold(): place for place in places}
    missing = list(report.missing_information)
    if len(unique) < settings.places_per_city:
        missing.append(f"Only {len(unique)} of {settings.places_per_city} requested places were supported.")
    report = report.model_copy(update={"important_places": list(unique.values()), "missing_information": missing})
    report = audit_report(report, city, bundle, state["discovery_results"])
    return {"city_reports": [report], "current_city": None, "current_city_raw_data": None}
