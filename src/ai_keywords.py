import json
import logging
import os
from typing import List, Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

FALLBACK_KEYWORDS = [
    "Kpop卡点女团舞 练功房",
    "抖音热舞挑战 辣妹穿搭",
    "街头爵士舞翻跳",
    "韩舞翻跳排练室",
    "热门舞蹈cover 卡点",
    "高颜值女团舞翻跳",
    "Urban街舞编舞 练功房",
]


def fetch_telegram_manual_keywords(bot_token: Optional[str]) -> List[str]:
    """
    Checks recent Telegram Bot updates to extract any custom keywords sent by the user.
    Recognizes messages starting with '/kw ' or '/keyword '.
    """
    if not bot_token:
        return []

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        resp = requests.get(url, params={"limit": 10, "timeout": 5}, timeout=10)
        if resp.status_code != 200:
            return []

        data = resp.json()
        if not data.get("ok"):
            return []

        keywords = []
        for item in data.get("result", []):
            msg = item.get("message", {})
            text = msg.get("text", "").strip()
            if not text:
                continue
            if text.startswith("/kw "):
                kw = text.replace("/kw ", "").strip()
                if kw:
                    keywords.append(kw)
            elif text.startswith("/keyword "):
                kw = text.replace("/keyword ", "").strip()
                if kw:
                    keywords.append(kw)

        if keywords:
            logger.info("Found %d manual keywords from Telegram: %s", len(keywords), keywords)
        return keywords
    except Exception as e:
        logger.warning("Could not fetch Telegram updates for manual keywords: %s", e)
        return []


def filter_available_models(client, candidate_models: List[str]) -> List[str]:
    """
    Queries client.models.list() to filter out models that are unavailable or 404
    for the current API key, keeping only valid models in preference order.
    """
    try:
        available_names = set()
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") and m.name else ""
            if name:
                available_names.add(name)
        if available_names:
            matched = [m for m in candidate_models if m in available_names or f"models/{m}" in available_names]
            if matched:
                logger.info("Verified active models via API: %s", matched)
                return matched
    except Exception as e:
        logger.debug("Could not query client.models.list() (%s); using original candidates.", e)
    return candidate_models


def generate_chinese_keywords_with_gemini(
    api_key: Optional[str],
    seed_categories: List[str],
    candidate_models: Optional[List[str]] = None,
    strategy: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Generates trending Chinese dance search keywords combining 3 strategic dimensions:
    [Dance Style / Trend] + [Outfit / Visual Aesthetic] + [Setting / Beat Drop].
    """
    if not api_key:
        logger.info("No GEMINI_API_KEY provided; utilizing fallback curated keywords.")
        return FALLBACK_KEYWORDS

    if not candidate_models:
        candidate_models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash"]

    strat_kws = (strategy or {}).get("keyword_generation_strategy", {})
    fashion_mods = strat_kws.get("fashion_visual_modifiers", ["辣妹热舞", "穿搭跳舞", "高颜值翻跳", "舞台造型"])
    setting_mods = strat_kws.get("setting_vibe_modifiers", ["练功房", "排练室", "街头翻跳", "卡点"])

    prompt = (
        f"You are the Lead Content & SEO Strategist for 'Dance Cover Universe' YouTube Shorts.\n"
        f"Mission: Discover viral-potential vertical dance covers featuring attractive dancers, stylish fashion, clean studio/street backdrops, and impressive choreography.\n"
        f"Target Categories: {', '.join(seed_categories)}.\n"
        f"Aesthetic/Fashion Modifiers: {', '.join(fashion_mods)}.\n"
        f"Setting/Vibe Modifiers: {', '.join(setting_mods)}.\n\n"
        f"Task: Generate 6 ultra-targeted trending Chinese search queries for Douyin vertical dance videos.\n"
        f"Combine 2-3 dimensions in each query: [Dance Style / Hot Challenge] + [Outfit / Visual Style] + [Setting / Beat Drop].\n"
        f"Examples: 'Kpop卡点女团舞 练功房', '街头辣妹爵士舞', '爆款热舞穿搭', '韩舞翻跳排练室', '高颜值编舞翻跳'.\n"
        f"Output ONLY a raw JSON array of strings, e.g. [\"关键词1\", \"关键词2\"]. No extra words or markdown notes."
    )

    from google import genai
    client = genai.Client(api_key=api_key)
    active_candidates = filter_available_models(client, candidate_models)

    for model_name in active_candidates:
        try:
            logger.info("Attempting keyword generation using model '%s'...", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            parsed = json.loads(text)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                logger.info("Successfully generated %d keywords from '%s': %s", len(parsed), model_name, parsed)
                return parsed
        except Exception as e:
            logger.warning("Model '%s' failed for keyword generation: %s. Trying next candidate...", model_name, e)

    logger.warning("All candidate models failed for keyword generation. Utilizing fallback curated keywords.")
    return FALLBACK_KEYWORDS


def load_topics_config(config_path: str = "config/topics.json") -> Optional[Dict[str, Any]]:
    """
    Attempts to load structured topics from config/topics.json.
    Returns parsed dictionary if valid, or None if missing/invalid.
    """
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "categories" in data:
                    logger.info("Loaded structured topics configuration from %s", config_path)
                    return data
    except Exception as e:
        logger.warning("Could not read topics config from %s: %s", config_path, e)
    return None


def get_search_keywords(
    gemini_key: Optional[str],
    telegram_token: Optional[str],
    seed_categories: List[str],
    candidate_models: Optional[List[str]] = None,
    topics_path: str = "config/topics.json",
) -> List[str]:
    """
    Combines Telegram manual keywords (if any) and AI generated keywords.
    Prioritizes categories and guidance defined in config/topics.json if present.
    """
    manual = fetch_telegram_manual_keywords(telegram_token)
    if manual:
        return manual

    topics = load_topics_config(topics_path)
    active_categories = seed_categories
    curated_fallback: List[str] = []

    if topics:
        cats = topics.get("categories", [])
        if cats:
            # Extract category names for the prompt
            active_categories = [c.get("name", "") for c in cats if isinstance(c, dict) and c.get("name")]
            # Extract curated queries from categories for fallback
            for c in cats:
                if isinstance(c, dict) and "douyin_queries" in c:
                    curated_fallback.extend(c["douyin_queries"])

    from .config_loader import load_channel_strategy
    strategy = load_channel_strategy()
    generated = generate_chinese_keywords_with_gemini(gemini_key, active_categories, candidate_models, strategy=strategy)
    if generated:
        return generated

    return curated_fallback if curated_fallback else FALLBACK_KEYWORDS
