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
    Recognizes messages starting with '/kw ' or general text queries.
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


def generate_chinese_keywords_with_gemini(
    api_key: Optional[str],
    seed_categories: List[str],
    model_name: str = "gemini-2.5-flash",
) -> List[str]:
    """
    Calls Gemini API with high RPD to generate trending Chinese dance search keywords.
    """
    if not api_key:
        logger.info("No GEMINI_API_KEY provided; utilizing fallback curated keywords.")
        return FALLBACK_KEYWORDS

    prompt = (
        f"You are a music & dance trend specialist. The channel curates top Douyin/TikTok dance covers.\n"
        f"Categories: {', '.join(seed_categories)}.\n"
        f"Generate 6-8 specific, trending Chinese search keywords suitable for finding Douyin vertical dance cover videos.\n"
        f"Examples: 'Kpop女团舞翻跳', '热门编舞翻跳', '抖音热舞挑战', '街舞Cover'.\n"
        f"Return ONLY a valid JSON list of strings, e.g. [\"关键词1\", \"关键词2\"]. No markdown, no commentary."
    )

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        text = response.text.strip()
        # Clean potential markdown wrapping
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            logger.info("Generated %d keywords from Gemini: %s", len(parsed), parsed)
            return parsed
    except Exception as e:
        logger.warning("Gemini keyword generation error: %s. Using fallback keywords.", e)

    return FALLBACK_KEYWORDS


def get_search_keywords(
    gemini_key: Optional[str],
    telegram_token: Optional[str],
    seed_categories: List[str],
    gemini_model: str = "gemini-2.5-flash",
) -> List[str]:
    """Combines Telegram manual keywords (if any) and Gemini generated keywords."""
    manual = fetch_telegram_manual_keywords(telegram_token)
    if manual:
        return manual
    return generate_chinese_keywords_with_gemini(gemini_key, seed_categories, gemini_model)
