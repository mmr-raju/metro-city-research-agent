"""Deterministic citation boundaries; semantic grounding still depends on extraction."""
import re
from decimal import Decimal

from errors import EvidenceError
from schemas import CityCandidate, CityReport, CityResearchBundle, SearchResult, SourceReference

MISSING = "Data not found in the retrieved sources"


def city_key(city: CityCandidate) -> str:
    return f"{city.country.casefold()}::{city.metro_or_urban_area_name.casefold()}"


def require_urls(urls, results: list[SearchResult]) -> None:
    allowed = {str(r.url) for r in results if r.snippet.strip()}
    if not {str(url) for url in urls}.issubset(allowed):
        raise EvidenceError("A citation was not found in the relevant retrieved evidence. Run research again.")


def population_supported(city: CityCandidate, results: list[SearchResult]) -> bool:
    """Check a figure and its year coexist in a cited snippet, including scaled figures.

    This catches invented numbers, but cannot prove which entity a passage describes.
    """
    for row in results:
        if str(row.url) not in {str(url) for url in city.source_urls}:
            continue
        text = row.snippet.replace(",", "").replace("\u00a0", "")
        if not re.search(rf"\b{city.population_year}\b", text):
            continue
        figures = set()
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(million|billion|thousand)?\b", text, re.I):
            scale = {"million": 1000000, "billion": 1000000000, "thousand": 1000}.get((match[2] or "").lower(), 1)
            figures.add(Decimal(match[1]) * scale)
        if city.population in figures:
            return True
    return False


def audit_report(report: CityReport, city: CityCandidate, bundle: CityResearchBundle,
                 discovery_results: list[SearchResult]) -> CityReport:
    if report.city != city or bundle.city_name != city.city_name or bundle.country != city.country:
        raise EvidenceError("City identity changed during analysis. Run research again.")
    require_urls(city.source_urls, discovery_results)
    for place in report.important_places:
        require_urls(place.source_urls, bundle.places)
    require_urls(report.best_time_to_visit.source_urls, bundle.timing)
    require_urls(report.getting_around.source_urls, bundle.transportation)

    # Missing sections cannot carry unsupported recommendations, even if a model tried.
    timing, transport = report.best_time_to_visit, report.getting_around
    missing = list(report.missing_information)
    if not timing.source_urls:
        timing = type(timing)(recommended_months=[], summary=MISSING,
                              weather_considerations=MISSING, crowd_or_price_considerations=MISSING,
                              source_urls=[])
        missing.append("Best time to visit: " + MISSING)
    if not transport.source_urls:
        transport = type(transport)(recommended_primary_mode=MISSING, explanation=MISSING,
                                    public_transport_options=[], alternatives=[], practical_tips=[],
                                    accessibility_or_safety_notes=[], source_urls=[])
        missing.append("Getting around: " + MISSING)
    if not report.important_places:
        missing.append("Important places: " + MISSING)

    supports: dict[str, list[str]] = {}
    for url in city.source_urls:
        supports.setdefault(str(url), []).append("Population, year and area definition")
    for place in report.important_places:
        for url in place.source_urls:
            supports.setdefault(str(url), []).append(f"Place: {place.name}; description and reason to visit")
    for label, urls in (("Best time to visit", timing.source_urls), ("Local transportation", transport.source_urls)):
        for url in urls:
            supports.setdefault(str(url), []).append(label)
    all_results = [*discovery_results, *bundle.all_results()]
    require_urls([s.url for s in report.sources], all_results)
    lookup = {str(row.url): row for row in reversed(all_results)}
    # Metadata is taken from retrieval, never from model-generated publisher/date fields.
    sources = [SourceReference(title=lookup[url].title, url=lookup[url].url,
                               publisher=lookup[url].publisher, accessed_at=lookup[url].accessed_at,
                               supports=list(dict.fromkeys(claims))) for url, claims in supports.items()]
    confidence = report.confidence
    if missing or city.confidence == "low":
        confidence = "low"
    elif city.confidence == "medium" and confidence == "high":
        confidence = "medium"
    return report.model_copy(update={"sources": sources, "missing_information": list(dict.fromkeys(missing)),
                                     "best_time_to_visit": timing, "getting_around": transport,
                                     "confidence": confidence})
