import operator
from typing import Annotated, TypedDict

from schemas import CityCandidate, CityReport, CityResearchBundle, CountryResearchReport, SearchResult


class ResearchState(TypedDict, total=False):
    input_country: str
    normalized_country: str
    discovery_raw_data: str
    discovery_results: list[SearchResult]
    discovered_cities: list[CityCandidate]
    city_queue: list[CityCandidate]
    current_city: CityCandidate | None
    current_city_raw_data: CityResearchBundle | None
    city_reports: Annotated[list[CityReport], operator.add]
    warnings: Annotated[list[str], operator.add]
    # Per-city audit trail survives clearing temporary state; never enters analyst prompts.
    evidence_by_city: dict[str, CityResearchBundle]
    ranking_basis: str
    population_data_note: str
    final_report: CountryResearchReport | None


def initial_state(country: str) -> ResearchState:
    return {"input_country": country, "city_queue": [], "city_reports": [], "warnings": [],
            "current_city": None, "current_city_raw_data": None,
            "evidence_by_city": {}, "final_report": None}
