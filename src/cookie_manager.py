import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict
import requests

logger = logging.getLogger(__name__)


def generate_netscape_cookie_content(cookies: Dict[str, str], domain: str = ".douyin.com") -> str:
    """Formats a dictionary of cookies into Netscape HTTP Cookie File format."""
    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated automatically for Douyin guest session",
        "",
    ]
    expires = int(time.time()) + 86400 * 30  # 30 days
    for name, value in cookies.items():
        if value:
            # domain, domain_specified, path, secure, expires, name, value
            lines.append(f"{domain}\tTRUE\t/\tFALSE\t{expires}\t{name}\t{value}")
    return "\n".join(lines) + "\n"


def fetch_douyin_guest_cookies() -> Dict[str, str]:
    """
    Acquires fresh guest cookies (specifically 'ttwid' and session tokens) from Douyin/ByteDance services.
    Does NOT require a logged-in account.
    """
    cookies: Dict[str, str] = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # Method 1: Request ttwid directly from ByteDance union register service
    ttwid_url = "https://ttwid.bytedance.com/ttwid/union/register/"
    ttwid_payload = {
        "region": "cn",
        "aid": 1768,
        "needFid": "false",
        "service": "www.ixigua.com",
        "migrate_info": {"ticket": "", "source": "node"},
        "cbUrlProtocol": "https",
        "union": "true",
    }
    try:
        resp = requests.post(ttwid_url, json=ttwid_payload, headers=headers, timeout=8)
        for c in resp.cookies:
            cookies[c.name] = c.value
        if "ttwid" in cookies:
            logger.info("Successfully acquired 'ttwid' cookie from ByteDance union service.")
    except Exception as e:
        logger.debug("ByteDance union register request failed: %s", e)

    # Method 2: Visit Douyin home page session handshake
    try:
        session = requests.Session()
        session.headers.update(headers)
        resp2 = session.get("https://www.douyin.com/", timeout=10)
        for c in resp2.cookies:
            cookies[c.name] = c.value
        for c in session.cookies:
            cookies[c.name] = c.value
        logger.info("Douyin session handshake completed. Extracted cookies: %s", list(cookies.keys()))
    except Exception as e:
        logger.warning("Douyin home handshake failed: %s", e)

    return cookies


def ensure_douyin_cookie_file(output_dir: Path, force_refresh: bool = False) -> Optional[Path]:
    """
    Ensures a valid Netscape cookie file exists in output_dir.
    Checks environment variable DOUYIN_COOKIES first; if not present, auto-generates guest cookies.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = output_dir / "douyin_cookies.txt"

    if cookie_path.exists() and not force_refresh:
        # Check if file has content
        if cookie_path.stat().st_size > 50:
            return cookie_path

    # 1. Check if user provided raw Netscape cookies or cookie string via env
    raw_env_cookies = os.getenv("DOUYIN_COOKIES")
    if raw_env_cookies:
        logger.info("Using DOUYIN_COOKIES provided via environment variable.")
        if "# Netscape" in raw_env_cookies:
            cookie_path.write_text(raw_env_cookies, encoding="utf-8")
        else:
            # Parse key=val; format
            cookie_dict = {}
            for item in raw_env_cookies.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    cookie_dict[k.strip()] = v.strip()
            content = generate_netscape_cookie_content(cookie_dict)
            cookie_path.write_text(content, encoding="utf-8")
        return cookie_path

    # 2. Automatically generate guest cookies
    logger.info("Auto-generating fresh Douyin guest cookies...")
    cookies = fetch_douyin_guest_cookies()
    if cookies:
        content = generate_netscape_cookie_content(cookies)
        cookie_path.write_text(content, encoding="utf-8")
        logger.info("Wrote fresh Netscape cookies to: %s", cookie_path)
        return cookie_path

    logger.warning("Could not obtain Douyin guest cookies; cookie file may be empty.")
    return None
