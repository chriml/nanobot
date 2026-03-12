from __future__ import annotations

import httpx
import pytest

from nanobot.agent.tools.web import WebSearchTool


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, dict, dict, float]] = []

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, *, params: dict, headers: dict, timeout: float) -> _FakeResponse:
        self.calls.append((url, params, headers, timeout))
        return _FakeResponse(
            {
                "results": [
                    {
                        "title": "SearXNG",
                        "url": "https://docs.searxng.org/",
                        "content": "Search API docs",
                    },
                    {
                        "title": "Nanobot",
                        "url": "https://github.com/HKUDS/nanobot",
                        "content": "Project repository",
                    },
                ]
            }
        )


@pytest.mark.asyncio
async def test_web_search_uses_searxng_json_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, _FakeAsyncClient] = {}

    def _build_client(**kwargs) -> _FakeAsyncClient:
        client = _FakeAsyncClient(**kwargs)
        seen["client"] = client
        return client

    monkeypatch.setattr(httpx, "AsyncClient", _build_client)
    tool = WebSearchTool(base_url="http://searxng:8080", max_results=2)

    result = await tool.execute("nanobot search", count=10)

    assert "1. SearXNG" in result
    assert "2. Nanobot" in result
    assert seen["client"].kwargs == {"proxy": None}
    assert seen["client"].calls == [
        (
            "http://searxng:8080/search",
            {"q": "nanobot search", "format": "json"},
            {"Accept": "application/json"},
            10.0,
        )
    ]


@pytest.mark.asyncio
async def test_web_search_reports_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    class _EmptyClient(_FakeAsyncClient):
        async def get(self, url: str, *, params: dict, headers: dict, timeout: float) -> _FakeResponse:
            return _FakeResponse({"results": []})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _EmptyClient(**kwargs))
    tool = WebSearchTool(base_url="http://localhost:8080")

    result = await tool.execute("nope")

    assert result == "No results for: nope"
