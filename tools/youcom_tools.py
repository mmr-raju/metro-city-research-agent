from langchain_core.tools import BaseTool, tool

from clients.youcom_client import YouComClient


def create_search_tool(client: YouComClient) -> BaseTool:
    @tool
    def youcom_web_search(query: str, count: int = 8) -> list[dict]:
        """Search the web; return distinct results with title, URL, snippet and publisher."""
        return [result.model_dump(mode="json") for result in client.search(query, count)]

    return youcom_web_search
