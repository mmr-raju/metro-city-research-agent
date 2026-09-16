from langchain_core.tools import BaseTool

from config import Settings
from errors import EvidenceError
from evidence import city_key
from nodes.common import Progress, run_searches
from schemas import CityResearchBundle
from state import ResearchState


def researcher_node(state: ResearchState, *, search: BaseTool, settings: Settings,
                    progress: Progress) -> dict:
    if not state["city_queue"]:
        raise EvidenceError("The city research queue is unexpectedly empty.")
    city, *remaining = state["city_queue"]
    location = f"{city.city_name}, {city.country} ({city.metro_or_urban_area_name})"
    groups = {
        "places": [f"most important places to visit in {location} official tourism",
                   f"top cultural historical attractions in {location}",
                   f"best landmarks museums neighborhoods in {location}"],
        "timing": [f"best months to visit {location} weather crowds",
                   f"{location} climate seasons official tourism",
                   f"{location} peak tourist season and rainy season"],
        "transportation": [f"best way for tourists to get around {location}",
                           f"{location} official public transportation visitor guide",
                           f"{location} metro bus taxi rideshare transport options"],
    }
    collected = {}
    warnings = []
    for section, queries in groups.items():
        progress(f"Researching {city.city_name}: {section}")
        results, failures = run_searches(search, queries, settings, progress=progress)
        collected[section] = results
        warnings.extend(failures)
    bundle = CityResearchBundle(city_name=city.city_name, country=city.country, **collected)
    return {"city_queue": remaining, "current_city": city, "current_city_raw_data": bundle,
            "evidence_by_city": {**state.get("evidence_by_city", {}), city_key(city): bundle},
            "warnings": warnings}
