import json
import logging
from typing import List, Optional
import requests

logger = logging.getLogger(__name__)

FALLBACK_KEYWORDS = [
    "Kpop舞蹈翻跳",
    "抖音热舞挑战",
    "女团舞翻跳",
    "街舞编舞翻跳",
    "热门舞蹈cover",
    "爵士舞翻跳",
    "男团舞翻跳",
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
) -> List[str]:
    """
    Generates trending Chinese dance search keywords.
    Tries candidate models sequentially (e.g. gemini-3.1-flash-lite -> gemini-3.5-flash-lite).
    """
    if not api_key:
        logger.info("No GEMINI_API_KEY provided; utilizing fallback curated keywords.")
        return FALLBACK_KEYWORDS

    if not candidate_models:
        candidate_models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash"]

    prompt = (
        f"Categories: {', '.join(seed_categories)}.\n"
        f"Generate 6 specific trending Chinese search keywords to find Douyin vertical dance cover videos.\n"
        f"Examples: 'Kpop女团舞翻跳', '热门编舞翻跳', '抖音热舞挑战'.\n"
        f"Output ONLY a raw JSON array of strings, e.g. [\"关键词1\", \"关键词2\"]. No extra words."
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


def get_search_keywords(
    gemini_key: Optional[str],
    telegram_token: Optional[str],
    seed_categories: List[str],
    candidate_models: Optional[List[str]] = None,
) -> List[str]:
    """Combines Telegram manual keywords (if any) and AI generated keywords."""
    manual = fetch_telegram_manual_keywords(telegram_token)
    if manual:
        return manual
    return generate_chinese_keywords_with_gemini(gemini_key, seed_categories, candidate_models)
