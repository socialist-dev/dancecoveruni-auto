import re
import os
import json
import logging
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple
import requests

logger = logging.getLogger(__name__)


@dataclass
class SearchResultItem:
    url: str
    jina_title: str = ""
    jina_description: str = ""


@dataclass
class SearchReport:
    discovered_items: List[SearchResultItem] = field(default_factory=list)
    total_scraped: int = 0
    jina_tokens_used: int = 0
    jina_tokens_remaining: Optional[int] = None

    @property
    def discovered_urls(self) -> List[str]:
        """Backward compatibility helper property."""
        return [item.url for item in self.discovered_items]


# Strict canonical Douyin video regex: only match /video/<numeric_id>
CANONICAL_DOUYIN_REGEX = re.compile(r"https?://(?:www\.)?douyin\.com/video/(\d{15,25})")
# Fallback TikTok regex
CANONICAL_TIKTOK_REGEX = re.compile(r"https?://(?:www\.)?tiktok\.com/@[^/\s?#]+/video/(\d{15,25})")


# Short Douyin regex (v.douyin.com)
DOUYIN_SHORT_REGEX = re.compile(r"https?://v\.douyin\.com/[a-zA-Z0-9_-]+/?")


def resolve_short_link(short_url: str) -> Optional[str]:
    """Resolves short redirect links like https://v.douyin.com/xxx/ to full canonical URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        }
        resp = requests.head(short_url, headers=headers, allow_redirects=True, timeout=8)
        if resp.url and "douyin.com/video/" in resp.url:
            return resp.url
    except Exception as e:
        logger.debug("Failed resolving short link %s: %s", short_url, e)
    return None


def canonicalize_url(raw_url: str) -> Optional[str]:
    """
    Normalizes a video URL to the cleanest canonical format:
    e.g. 'https://www.douyin.com/video/7391234567890123456'
    Strips away trailing punctuation (.,:;…!?'\"/), whitespace, query parameters, trackers,
    resolves short links, and rejects non-video links.
    """
    if not raw_url:
        return None

    # Strip whitespace and trailing punctuation like '...', '…', '.', ',', ':', ';', '!', '?'
    cleaned = raw_url.strip().rstrip(".,:;…!?'\"/) \t\n")

    # If it's a short link like v.douyin.com/xxx/
    if "v.douyin.com" in cleaned:
        resolved = resolve_short_link(cleaned)
        if resolved:
            cleaned = resolved

    # Check Douyin
    douyin_match = CANONICAL_DOUYIN_REGEX.search(cleaned)
    if douyin_match:
        video_id = douyin_match.group(1)
        return f"https://www.douyin.com/video/{video_id}"

    # Check TikTok
    tiktok_match = CANONICAL_TIKTOK_REGEX.search(cleaned)
    if tiktok_match:
        return tiktok_match.group(0).split("?")[0].rstrip(".,:;…!?'\"/) \t\n")

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
        canonical = match.group(0).split("?")[0].rstrip(".,:;…!?'\"/) \t\n")
        if canonical not in seen:
            seen.add(canonical)
            urls.append(canonical)

    for match in DOUYIN_SHORT_REGEX.finditer(text):
        short_url = match.group(0)
        canonical = canonicalize_url(short_url)
        if canonical and canonical not in seen:
            seen.add(canonical)
            urls.append(canonical)

    return urls


def search_with_jina(keyword: str, api_key: Optional[str] = None, site: str = "douyin.com") -> Tuple[List[SearchResultItem], int, int, Optional[int]]:
    """
    Uses Jina Search (s.jina.ai) adhering strictly to jina-docs specifications:
    - X-Respond-With: no-content (avoids heavy page scraping, prevents read timeout)
    - X-Site: douyin.com or tiktok.com (restricts search directly to target video domain)
    - Accept: application/json (parses clean structured JSON results)
    Returns (valid_canonical_items, raw_scraped_count, tokens_used, remaining_tokens)
    """
    encoded_query = urllib.parse.quote_plus(keyword)
    url = f"https://s.jina.ai/{encoded_query}"

    headers = {
        "Accept": "application/json",
        "X-Respond-With": "no-content",
        "X-Site": site,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        logger.info("Querying Jina Search (s.jina.ai) for: '%s' (X-Site: %s)...", keyword, site)
        resp = requests.get(url, headers=headers, timeout=25)

        tokens = 0
        raw_token_header = resp.headers.get("x-usage-tokens") or resp.headers.get("x-ratelimit-tokens")
        if raw_token_header:
            try:
                tokens = int(raw_token_header)
            except (ValueError, TypeError):
                tokens = 0

        raw_remaining_header = (
            resp.headers.get("x-ratelimit-remaining-tokens")
            or resp.headers.get("x-ratelimit-remaining")
            or resp.headers.get("x-user-token-balance")
        )
        remaining = None
        if raw_remaining_header:
            try:
                remaining = int(raw_remaining_header)
            except (ValueError, TypeError):
                remaining = None

        if resp.status_code == 200:
            if tokens == 0:
                tokens = 10000  # Default base tokens per successful Jina search query

            content_type = resp.headers.get("content-type", "")
            found_items: List[SearchResultItem] = []
            seen: Set[str] = set()
            raw_count = 0

            if "application/json" in content_type:
                data = resp.json()
                items = data.get("data", []) if isinstance(data, dict) else []
                raw_count = len(items)
                for item in items:
                    raw_link = item.get("url") if isinstance(item, dict) else None
                    if raw_link:
                        canonical = canonicalize_url(raw_link)
                        if canonical and canonical not in seen:
                            seen.add(canonical)
                            found_items.append(
                                SearchResultItem(
                                    url=canonical,
                                    jina_title=item.get("title", "") if isinstance(item, dict) else "",
                                    jina_description=item.get("description", "") if isinstance(item, dict) else "",
                                )
                            )
            else:
                raw_urls = extract_video_urls_from_text(resp.text)
                raw_count = len(raw_urls)
                for u in raw_urls:
                    if u not in seen:
                        seen.add(u)
                        found_items.append(SearchResultItem(url=u))

            logger.info("Jina Search returned %d valid canonical video URLs (raw: %d, tokens: %d, remaining: %s) for '%s'", len(found_items), raw_count, tokens, remaining, keyword)
            return found_items, raw_count, tokens, remaining
        else:
            logger.warning("Jina Search returned status %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("Jina Search failed for keyword '%s': %s", keyword, e)

    return [], 0, 0, None


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
    topics_path: str = "config/topics.json",
) -> Tuple[List[SearchResultItem], SearchReport]:
    """
    Iterates through keywords to discover fresh canonical Douyin & TikTok video URLs.
    Filters out already processed URLs.
    Returns (discovered_items, search_report)
    """
    report = SearchReport()
    discovered_set: Set[str] = set(processed_urls)

    # 1. Primary: Douyin video search
    for kw in keywords:
        if len(report.discovered_items) >= max_needed:
            break

        found_items, raw_count, tokens, rem = search_with_jina(kw, jina_api_key, site="douyin.com")
        report.total_scraped += raw_count
        report.jina_tokens_used += tokens
        if rem is not None:
            report.jina_tokens_remaining = rem

        if not found_items and firecrawl_api_key:
            dork = f'site:douyin.com/video/ "{kw}"'
            fc_found = search_with_firecrawl(dork, firecrawl_api_key)
            report.total_scraped += len(fc_found)
            found_items = [SearchResultItem(url=u) for u in fc_found]

        for item in found_items:
            if item.url not in discovered_set:
                discovered_set.add(item.url)
                report.discovered_items.append(item)
                logger.info("Found fresh candidate: [%s]", item.url)
                if len(report.discovered_items) >= max_needed:
                    break

    # 2. Supplemental: TikTok Dance Cover search fallback if needed
    if len(report.discovered_items) < max_needed:
        logger.info("Discovering supplemental TikTok dance cover candidates (current: %d/%d)...", len(report.discovered_items), max_needed)
        tiktok_keywords = ["kpop dance cover", "trending dance choreo", "douyin dance challenge"]
        try:
            if os.path.exists(topics_path):
                with open(topics_path, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                    custom_tt = []
                    for c in t_data.get("categories", []):
                        if isinstance(c, dict):
                            for tag in c.get("tiktok_hashtags", []):
                                clean_tag = tag.lstrip("#")
                                if clean_tag and clean_tag not in custom_tt:
                                    custom_tt.append(clean_tag)
                    if custom_tt:
                        tiktok_keywords = custom_tt
        except Exception as e:
            logger.debug("Could not read TikTok hashtags from %s: %s", topics_path, e)

        for kw in tiktok_keywords:
            if len(report.discovered_items) >= max_needed:
                break
            found_tt, raw_tt_count, tt_tokens, tt_rem = search_with_jina(kw, jina_api_key, site="tiktok.com")
            report.total_scraped += raw_tt_count
            report.jina_tokens_used += tt_tokens
            if tt_rem is not None:
                report.jina_tokens_remaining = tt_rem

            for item in found_tt:
                if item.url not in discovered_set:
                    discovered_set.add(item.url)
                    report.discovered_items.append(item)
                    logger.info("Found fresh candidate (TikTok): [%s]", item.url)
                    if len(report.discovered_items) >= max_needed:
                        break

    logger.info(
        "Total fresh candidate URLs discovered: %d | Total raw scraped: %d | Jina tokens used: %d | Remaining: %s",
        len(report.discovered_items), report.total_scraped, report.jina_tokens_used, report.jina_tokens_remaining
    )
    return report.discovered_items, report
