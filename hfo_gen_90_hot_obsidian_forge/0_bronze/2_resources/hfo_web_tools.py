"""
HFO Gen90 — Web Research Tools
===============================
Provides web search and page fetching capabilities for swarm agents.
Uses DuckDuckGo for privacy-respecting search.

Pointer key: swarm.web_tools
Medallion: bronze
"""

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
from typing import Optional


def web_search(query: str, max_results: int = 10, region: str = "wt-wt") -> str:
    """
    Search the web using DuckDuckGo. Returns formatted results.
    Use this to find current information, news, documentation, etc.

    Args:
        query: The search query string
        max_results: Maximum number of results to return
        region: Region for results (wt-wt = worldwide)
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region=region, max_results=max_results))

        if not results:
            return f"No results found for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('href', 'No URL')}\n"
                f"    {r.get('body', 'No description')}"
            )
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search error: {e}"


def web_news(query: str, max_results: int = 10) -> str:
    """
    Search for recent news using DuckDuckGo News.

    Args:
        query: The news search query
        max_results: Maximum number of results
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))

        if not results:
            return f"No news found for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    Source: {r.get('source', 'Unknown')} | {r.get('date', 'No date')}\n"
                f"    URL: {r.get('url', 'No URL')}\n"
                f"    {r.get('body', 'No description')}"
            )
        return "\n\n".join(formatted)
    except Exception as e:
        return f"News search error: {e}"


def fetch_page(url: str, max_chars: int = 8000) -> str:
    """
    Fetch and extract readable text from a webpage.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (default 8000)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script, style, nav, footer elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... truncated]"

        return f"Content from {url}:\n\n{text}"
    except Exception as e:
        return f"Fetch error for {url}: {e}"


def search_and_summarize(query: str, max_results: int = 5) -> str:
    """
    Search the web and return results with brief context.
    Combines search results into a research-ready format.

    Args:
        query: Search query
        max_results: Number of results to include
    """
    search_results = web_search(query, max_results=max_results)
    return (
        f"=== Web Research: {query} ===\n\n"
        f"{search_results}\n\n"
        f"=== End Results ===\n"
        f"Use fetch_page(url) to read full content from any result above."
    )


# ── Tool definitions for Swarm agents ──────────────────────────
# These are the function objects that get passed to Swarm Agent definitions
SWARM_WEB_TOOLS = [web_search, web_news, fetch_page, search_and_summarize]


if __name__ == "__main__":
    # Quick test
    print("Testing web search...")
    results = web_search("latest popular ollama models 2025", max_results=5)
    print(results)
