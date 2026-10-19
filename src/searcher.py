import re
import logging
import urllib.parse
from typing import List, Set, Optional
import requests

logger = logging.getLogger(__name__)

# Strict canonical Douyin video regex: only match /video/<numeric_id>
CANONICAL_DOUYIN_REGEX = re.compile(r"https?://(?:www\.)?douyin\.com/video/(\d{15,25})")
# Fallback TikTok regex
CANONICAL_TIKTOK_REGEX = re.compile(r"https?://(?:www\.)?tiktok\.com/@[^/\s?#]+/video/(\d{15,25})")


def canonicalize_url(raw_url: str) -> Optional[str]:
    """
    Normalizes a video URL to the cleanest canonical format:
    e.g. 'https://www.douyin.com/video/7391234567890123456'
    Strips away query parameters, trackers, and rejects non-video links.
    """
    if not raw_url:
        return None

    # Check Douyin
    douyin_match = CANONICAL_DOUYIN_REGEX.search(raw_url)
    if douyin_match:
        video_id = douyin_match.group(1)
        return f"https://www.douyin.com/video/{video_id}"

    # Check TikTok
    tiktok_match = CANONICAL_TIKTOK_REGEX.search(raw_url)
    if tiktok_match:
        return tiktok_match.group(0).split("?")[0]

    return None


def extract_video_urls_from_text(text: str) -> List[str]:
    """Finds all unique canonical video URLs inside arbitrary text or markdown."""
    urls = []
    seen = set()

    for match in CANONICAL_DOUYIN_REGEX.finditer(text):
        canonical = f"https://www.douyin.com/video/{match.group(1)}"
        if canonical not in seen:
            seen.add(canonical)
            urls.append(canonical)

    for match in CANONICAL_TIKTOK_REGEX.finditer(text):
        canonical = match.group(0).split("?")[0]
        if canonical not in seen:
            seen.add(canonical)
            urls.append(canonical)

    return urls


def search_with_jina(keyword: str, api_key: Optional[str] = None) -> List[str]:
    """
    Uses Jina Search (s.jina.ai) adhering strictly to jina-docs specifications:
    - X-Respond-With: no-content (avoids heavy page scraping, prevents 20s read timeout)
    - X-Site: douyin.com (restricts search directly to douyin.com domain)
    - Accept: application/json (parses clean structured JSON results)
    """
    encoded_query = urllib.parse.quote_plus(keyword)
    url = f"https://s.jina.ai/{encoded_query}"

    headers = {
        "Accept": "application/json",
        "X-Respond-With": "no-content",
        "X-Site": "douyin.com",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        logger.info("Querying Jina Search (s.jina.ai) for: '%s' (X-Site: douyin.com)...", keyword)
        resp = requests.get(url, headers=headers, timeout=25)

        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            found_urls: List[str] = []
            seen: Set[str] = set()

            if "application/json" in content_type:
                data = resp.json()
                items = data.get("data", []) if isinstance(data, dict) else []
                for item in items:
                    raw_link = item.get("url") if isinstance(item, dict) else None
                    if raw_link:
                        canonical = canonicalize_url(raw_link)
                        if canonical and canonical not in seen:
                            seen.add(canonical)
                            found_urls.append(canonical)
            else:
                # Text/Markdown fallback
                found_urls = extract_video_urls_from_text(resp.text)

            logger.info("Jina Search returned %d valid canonical video URLs for '%s'", len(found_urls), keyword)
            return found_urls
        else:
            logger.warning("Jina Search returned status %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("Jina Search failed for keyword '%s': %s", keyword, e)

    return []


def search_with_firecrawl(dork_query: str, api_key: Optional[str]) -> List[str]:
    """Uses Firecrawl Search API as backup."""
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
            return extract_video_urls_from_text(str(data))
        else:
            logger.warning("Firecrawl Search returned status %d: %s", resp.status_code, resp.text[:200])
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
    Iterates through keywords to discover fresh canonical Douyin video URLs.
    Filters out already processed URLs.
    """
    discovered: List[str] = []
    discovered_set: Set[str] = set(processed_urls)

    for kw in keywords:
        if len(discovered) >= max_needed:
            break

        # 1. Primary: Jina Search with no-content and X-Site
        found = search_with_jina(kw, jina_api_key)

        # 2. Backup: Firecrawl if Jina returned empty
        if not found and firecrawl_api_key:
            dork = f'site:douyin.com/video/ "{kw}"'
            found = search_with_firecrawl(dork, firecrawl_api_key)

        for u in found:
            if u not in discovered_set:
                discovered_set.add(u)
                discovered.append(u)
                logger.info("Found fresh candidate: %s", u)
                if len(discovered) >= max_needed:
                    break

    logger.info("Total fresh candidate URLs discovered: %d", len(discovered))
    return discovered
