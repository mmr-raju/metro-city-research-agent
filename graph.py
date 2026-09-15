from functools import partial
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from config import Settings
from nodes.analyst import analyst_node
from nodes.common import Progress
from nodes.discovery import discovery_node
from nodes.finalizer import finalizer_node
from nodes.researcher import researcher_node
from state import ResearchState


def queue_router(state: ResearchState) -> Literal["researcher", "finalizer"]:
    return "researcher" if state.get("city_queue") else "finalizer"


def build_graph(llm: BaseChatModel, search: BaseTool, settings: Settings,
                progress: Progress | None = None):
    notify = progress or (lambda message: None)
    builder = StateGraph(ResearchState)
    builder.add_node("discovery", partial(discovery_node, llm=llm, search=search,
                                          settings=settings, progress=notify))
    builder.add_node("researcher", partial(researcher_node, search=search, settings=settings, progress=notify))
    builder.add_node("analyst", partial(analyst_node, llm=llm, settings=settings, progress=notify))
    builder.add_node("finalizer", partial(finalizer_node, progress=notify))
    builder.add_edge(START, "discovery")
    builder.add_edge("discovery", "researcher")
    builder.add_edge("researcher", "analyst")
    builder.add_conditional_edges("analyst", queue_router,
                                  {"researcher": "researcher", "finalizer": "finalizer"})
    builder.add_edge("finalizer", END)
    return builder.compile()
