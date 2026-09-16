import json
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from config import Settings
from countries import normalize_country
from errors import InsufficientRankingError, SearchError
from evidence import city_key, population_supported, require_urls
from nodes.common import Progress, extract, run_searches
from prompts import DISCOVERY_PROMPT
from schemas import DiscoveryExtraction
from state import ResearchState


def discovery_node(state: ResearchState, *, llm: BaseChatModel, search: BaseTool,
                   settings: Settings, progress: Progress) -> dict:
    country = normalize_country(state["input_country"])
    progress(f"Discovery: finding comparable urban/metro populations for {country}")
    results, warnings = run_searches(search, [
        f"{country} largest metropolitan areas by population latest",
        f"{country} largest urban agglomerations population UN",
        f"{country} census official statistics largest urban areas population",
        f"site:gov {country} metropolitan population cities",
    ], settings, progress=progress)
    if not any(row.snippet.strip() for row in results):
        if warnings:
            details = list(dict.fromkeys(w.split(": ", 1)[-1] for w in warnings))
            raise SearchError("Population discovery could not retrieve usable search evidence. " + " ".join(details))
        raise InsufficientRankingError(
            "Search completed but returned no usable population snippets. Try the full country name or retry with different search evidence.")
    raw = json.dumps([r.model_dump(mode="json") for r in results], ensure_ascii=False)
    data = extract(llm, DiscoveryExtraction, DISCOVERY_PROMPT,
                   {"country": country, "current_year": datetime.now(timezone.utc).year,
                    "search_results": json.loads(raw)}, progress=progress)
    cities = data.cities
    if len(cities) != 3:
        raise InsufficientRankingError("The retrieved evidence does not establish three recognized urban/metro areas. This country may have fewer than three; no cities were invented.")
    if (not data.ranking_supported or not data.consistent_definition or
            data.area_type == "unavailable" or not data.dataset_name.strip() or
            len({city.population_definition.casefold() for city in cities}) != 1):
        raise InsufficientRankingError("A consistent national top-three urban/metro dataset could not be established. Retry when better search evidence is available.")
    if len({city_key(city) for city in cities}) != 3 or any(city.country != country for city in cities):
        raise InsufficientRankingError("Discovery returned duplicate areas or a different country. Retry with the full country name.")
    for city in cities:
        require_urls(city.source_urls, results)
        if (city.population is None or city.population_year is None or
                city.population_year > datetime.now(timezone.utc).year or
                not population_supported(city, results)):
            raise InsufficientRankingError("Population figures and years could not be verified in the retrieved snippets. A reliable descending ranking is unavailable.")
        if "city proper" in city.population_definition.casefold().replace("-", " "):
            raise InsufficientRankingError("Only city-proper data was supplied; comparable urban/metro evidence is required.")
    ordered = sorted(cities, key=lambda city: city.population, reverse=True)
    warnings.extend(data.warnings)
    if len({c.population_year for c in cities}) > 1:
        warnings.append("Population estimates use different years and are not directly contemporaneous.")
    if data.area_type == "urban_agglomeration":
        warnings.append("Ranking uses an urban-agglomeration fallback rather than metropolitan boundaries.")
    if any(c.confidence != "high" for c in cities):
        warnings.append("Population ranking has evidence limitations; review each city's confidence notes.")
    return {"normalized_country": country, "discovery_raw_data": raw,
            "discovery_results": results, "discovered_cities": ordered,
            "city_queue": list(ordered), "warnings": warnings,
            "ranking_basis": f"{data.ranking_basis} Dataset: {data.dataset_name}. Definition: {ordered[0].population_definition}.",
            "population_data_note": data.population_data_note}
