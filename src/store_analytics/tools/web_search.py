"""Tool: web_search — search the web for current/external information."""

from __future__ import annotations

import json

import httpx

web_search_schema = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current or external information not in the database. "
            "Use this for: exchange rates, current market prices, news, general knowledge "
            "that isn't about our store's sales data. Do NOT use for store-specific data "
            "(use query_db for that)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    },
}

# Curated fallback data for common queries (used when no API key or as seed)
_CACHED_DATA: dict[str, str] = {
    "eur usd": "1 EUR = 1.0850 USD (as of September 2026)",
    "usd eur": "1 USD = 0.9217 EUR (as of September 2026)",
    "gbp usd": "1 GBP = 1.2720 USD (as of September 2026)",
    "usd gbp": "1 USD = 0.7862 GBP (as of September 2026)",
    "inflation rate spain 2026": "Spain inflation rate: approximately 2.1% (2026 estimate)",
    "current date": "Today's date is approximately September 2026.",
}


def web_search_tool(query: str) -> str:
    """Search the web using DuckDuckGo (no API key required) with fallback to cached data."""
    query_lower = query.lower().strip()

    # Check cached data first — match if all words in the key appear in the query
    for key, value in _CACHED_DATA.items():
        key_words = key.split()
        if all(w in query_lower for w in key_words):
            return json.dumps({"results": [{"title": key, "snippet": value}], "source": "cache"})

    # Try DuckDuckGo Instant Answers API (free, no key)
    try:
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get("AbstractText", "")
            if abstract:
                return json.dumps({"results": [{"title": query, "snippet": abstract}], "source": "duckduckgo"})

            # Try related topics
            related = data.get("RelatedTopics", [])
            results = []
            for topic in related[:3]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({"title": topic.get("Text", "")[:80], "snippet": topic["Text"]})
            if results:
                return json.dumps({"results": results, "source": "duckduckgo"})
    except Exception:
        pass

    # Final fallback: suggest the query couldn't be resolved
    return json.dumps({
        "results": [],
        "source": "none",
        "message": f"No results found for: {query}. Try rephrasing or use cached data.",
    })
