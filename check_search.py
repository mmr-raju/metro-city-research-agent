"""Check the configured search connection without printing keys or response bodies."""
import argparse

import httpx
from pydantic import ValidationError

from clients.youcom_client import YouComClient
from config import Settings
from errors import ResearchError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", default="Japan")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        with YouComClient(settings) as client:
            response = client._client.post(settings.youcom_search_path, json={
                "query": f"{args.country} largest metropolitan areas population census", "count": 3})
            print(f"Search HTTP status: {response.status_code}")
            if not response.is_success:
                print("The endpoint rejected the request; no response body or credentials displayed.")
                return 1
            try:
                rows = client._normalize(response.json())
            except ValidationError as exc:
                for error in exc.errors():
                    print("Invalid result field:", ".".join(map(str, error["loc"])), error["type"])
                return 1
            except (ValueError, TypeError, KeyError):
                print("Search returned a response that does not match the expected results schema.")
                return 1
            print(f"Results: {len(rows)}; with usable snippets: {sum(bool(r.snippet.strip()) for r in rows)}")
            return 0 if any(r.snippet.strip() for r in rows) else 1
    except ResearchError as exc:
        print(str(exc))
        return 1
    except httpx.RequestError:
        print("Search connection failed. Check network access and timeout settings.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
