import re
import logging
from typing import List, Set, Optional
import requests

logger = logging.getLogger(__name__)

DOUYIN_VIDEO_REGEX = re.compile(
    r"https?://(?:www\.)?douyin\.com/video/(\d+)|https?://v\.douyin\.com/([a-zA-Z0-9_-]+)/?"
)
TIKTOK_VIDEO_REGEX = re.compile(
    r"https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)"
)


def extract_video_urls(text: str) -> List[str]:
    """Finds all unique Douyin and TikTok video URLs inside arbitrary text/markdown."""
    urls = []
    seen = set()

    # Match standard Douyin /video/123456789
    for match in re.finditer(r"https?://(?:www\.)?douyin\.com/video/(\d+)", text):
        url = f"https://www.douyin.com/video/{match.group(1)}"
        if url not in seen:
            seen.add(url)
            urls.append(url)

    # Match short link https://v.douyin.com/xyz/
    for match in re.finditer(r"https?://v\.douyin\.com/[a-zA-Z0-9_-]+/?", text):
        url = match.group(0).rstrip("/")
        if url not in seen:
            seen.add(url)
            urls.append(url)

    # Match TikTok
    for match in re.finditer(r"https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.-]+/video/(\d+)", text):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls


def search_with_jina(dork_query: str, api_key: Optional[str] = None) -> List[str]:
    """Uses Jina Search (s.jina.ai) to search web and scrape URLs."""
    url = f"https://s.jina.ai/{dork_query}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            return extract_video_urls(resp.text)
        else:
            logger.warning("Jina Search returned status %d", resp.status_code)
    except Exception as e:
        logger.warning("Jina Search failed: %s", e)
    return []


def search_with_firecrawl(dork_query: str, api_key: Optional[str]) -> List[str]:
    """Uses Firecrawl Search API to search web."""
    if not api_key:
        return []

    url = "https://api.firecrawl.dev/v1/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"query": dork_query, "limit": 10}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            combined_text = str(data)
            return extract_video_urls(combined_text)
        else:
            logger.warning("Firecrawl Search returned status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Firecrawl Search failed: %s", e)
    return []


def discover_video_urls(
    keywords: List[str],
    processed_urls: Set[str],
    jina_api_key: Optional[str] = None,
    firecrawl_api_key: Optional[str] = None,
    max_needed: int = 15,
) -> List[str]:
    """
    Executes Google Dorking queries for each keyword to find candidate Douyin/TikTok URLs.
    Filters out already processed URLs.
    """
    discovered: List[str] = []
    discovered_set: Set[str] = set(processed_urls)

    for kw in keywords:
        if len(discovered) >= max_needed:
            break

        dork = f'site:douyin.com/video/ "{kw}"'
        logger.info("Executing Dorking search: %s", dork)

        # 1. Try Jina Search
        found = search_with_jina(dork, jina_api_key)

        # 2. Try Firecrawl if Jina found nothing
        if not found and firecrawl_api_key:
            found = search_with_firecrawl(dork, firecrawl_api_key)

        for u in found:
            if u not in discovered_set:
                discovered_set.add(u)
                discovered.append(u)
                logger.info("Found new candidate URL: %s", u)
                if len(discovered) >= max_needed:
                    break

    logger.info("Total fresh candidate URLs discovered: %d", len(discovered))
    return discovered
