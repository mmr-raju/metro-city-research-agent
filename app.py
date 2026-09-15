"""Run with: streamlit run app.py"""
import streamlit as st

from clients.youcom_client import YouComClient
from config import Settings
from countries import normalize_country
from errors import ResearchError
from graph import build_graph
from llm_factory import create_llm
from schemas import CountryResearchReport
from state import initial_state
from tools.youcom_tools import create_search_tool


def citation_links(urls) -> None:
    for index, url in enumerate(urls, 1):
        st.link_button(f"Supporting source {index}", str(url))


def render_report(report: CountryResearchReport) -> None:
    st.header(report.country)
    st.subheader("How the cities were selected")
    st.write(report.ranking_basis)
    st.info(report.population_data_note)
    for warning in report.warnings:
        st.warning(warning)
    for rank, result in enumerate(report.cities, 1):
        city = result.city
        with st.container(border=True):
            st.subheader(f"{rank}. {city.city_name}")
            st.write(city.metro_or_urban_area_name)
            population = f"{city.population:,}" if city.population is not None else "Unavailable"
            st.metric(f"Population ({city.population_year or 'year unavailable'})", population)
            st.caption(f"{city.population_definition} · Population confidence: {city.confidence} · Travel confidence: {result.confidence}")
            if city.notes:
                st.write(city.notes)
            with st.expander("Population sources"):
                citation_links(city.source_urls)
            st.markdown("#### Important places")
            if not result.important_places:
                st.write("Data not found in the retrieved sources")
            for place in result.important_places:
                st.write(f"{place.name} — {place.category}")
                st.write(place.short_description)
                st.write(place.why_visit)
                with st.expander(f"Sources for {place.name}"):
                    citation_links(place.source_urls)
            left, right = st.columns(2)
            with left:
                timing = result.best_time_to_visit
                st.markdown("#### Best time to visit")
                if timing.recommended_months:
                    st.write(", ".join(timing.recommended_months))
                st.write(timing.summary)
                st.write("Weather: " + timing.weather_considerations)
                st.write("Crowds and prices: " + timing.crowd_or_price_considerations)
                with st.expander("Visit timing sources"):
                    citation_links(timing.source_urls)
            with right:
                transit = result.getting_around
                st.markdown("#### Getting around")
                st.write(transit.recommended_primary_mode)
                st.write(transit.explanation)
                for label, items in (("Public transport", transit.public_transport_options),
                                     ("Alternatives", transit.alternatives),
                                     ("Practical tips", transit.practical_tips),
                                     ("Accessibility and safety", transit.accessibility_or_safety_notes)):
                    if items:
                        st.write(label)
                        for item in items:
                            st.write("• " + item)
                with st.expander("Transport sources"):
                    citation_links(transit.source_urls)
            if result.missing_information:
                st.warning("Some information could not be established from the retrieved evidence.")
                for missing in result.missing_information:
                    st.write("• " + missing)
            with st.expander(f"All sources for {city.city_name}"):
                for source in result.sources:
                    st.link_button(source.title, str(source.url))
                    st.caption(f"{source.publisher or 'Publisher unavailable'} · Accessed {source.accessed_at.isoformat()}")
                    st.write("Supports: " + "; ".join(source.supports))
    st.caption(f"Generated {report.generated_at.isoformat()}")
    st.download_button("Download complete report (JSON)", report.model_dump_json(indent=2),
                       file_name="country-city-research.json", mime="application/json")


def main() -> None:
    st.set_page_config(page_title="Country & City Research", page_icon="🌍", layout="wide")
    st.title("Country & City Research")
    st.write("Explore the three largest urban or metro areas with cited places, visit timing and local transport guidance.")
    with st.form("research"):
        country = st.text_input("Country", placeholder="Japan, Brazil, UK…", max_chars=100)
        submitted = st.form_submit_button("Run Research", type="primary")
    if submitted:
        st.session_state.pop("report", None)
        try:
            normalize_country(country)  # Input errors should appear even before keys are configured.
            settings = Settings.from_env()
            llm = create_llm(settings)
            with st.status("Starting research…", expanded=True) as status:
                progress_bar = st.progress(0.0)
                completed = 0

                def update(message: str) -> None:
                    status.update(label=message)

                with YouComClient(settings) as client:
                    workflow = build_graph(llm, create_search_tool(client), settings, update)
                    for event in workflow.stream(initial_state(country),
                                                  config={"recursion_limit": 20}, stream_mode="updates"):
                        for node, change in event.items():
                            completed += 1
                            progress_bar.progress(min(completed / 8, 1.0))
                            if node == "discovery":
                                st.write("Cities selected: " + ", ".join(c.city_name for c in change["city_queue"]))
                            if node == "analyst":
                                st.write("Completed " + change["city_reports"][0].city.city_name)
                            if node == "finalizer":
                                st.session_state["report"] = change["final_report"]
                status.update(label="Research complete", state="complete", expanded=False)
        except ResearchError as exc:
            st.error(str(exc))
        except Exception:
            # Never render SDK errors: they can contain request details or credentials.
            st.error("Research could not complete. Check your configuration and model access, then retry.")
    if "report" in st.session_state:
        render_report(st.session_state["report"])


if __name__ == "__main__":
    main()
