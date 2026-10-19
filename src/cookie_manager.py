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


def parse_and_validate_cookies(raw_text: str) -> Optional[str]:
    """
    Parses arbitrary cookie representations into a valid Netscape HTTP Cookie format:
    1. Standard Netscape tab-separated format (with or without # Netscape header).
    2. JSON array exported from browser extensions (e.g. EditThisCookie, Cookie-Editor).
    3. Semicolon-separated key=value strings (e.g. from browser document.cookie or request headers).
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned_raw = raw_text.strip()
    valid_lines = []
    found_tokens = []
    KEY_TOKENS = ["ttwid", "passport_csrf_token", "__ac_nonce", "odin_tt", "sessionid", "sid_guard", "passport_auth_status"]

    # --- Mode 1: JSON format (starts with '[' or '{') ---
    if cleaned_raw.startswith("[") or cleaned_raw.startswith("{"):
        try:
            import json
            data = json.loads(cleaned_raw)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name")
                        val = item.get("value")
                        if not name or val is None:
                            continue
                        domain = item.get("domain") or ".douyin.com"
                        flag = "TRUE" if domain.startswith(".") else "FALSE"
                        path = item.get("path") or "/"
                        secure = "TRUE" if item.get("secure") else "FALSE"
                        expires = int(item.get("expirationDate") or item.get("expires") or (time.time() + 86400 * 30))
                        valid_lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{val}")
                        if name in KEY_TOKENS:
                            found_tokens.append(name)
                if valid_lines:
                    logger.info("Parsed %d cookies from JSON format. Key tokens detected: %s", len(valid_lines), list(set(found_tokens)))
                    return "# Netscape HTTP Cookie File\n\n" + "\n".join(valid_lines) + "\n"
        except Exception as e:
            logger.debug("Failed parsing DOUYIN_COOKIES as JSON (%s), falling back...", e)

    # --- Mode 2: Netscape format (tab-separated) ---
    if "\t" in cleaned_raw:
        lines = cleaned_raw.splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                valid_lines.append(stripped)
                continue
            parts = stripped.split("\t")
            if len(parts) >= 7:
                valid_lines.append(stripped)
                c_name = parts[5]
                if c_name in KEY_TOKENS:
                    found_tokens.append(c_name)
            elif len(parts) >= 6:
                # Add default secure flag if missing
                valid_lines.append(stripped)

        if valid_lines:
            header_exists = any("Netscape HTTP Cookie File" in l for l in valid_lines[:3])
            content = ("" if header_exists else "# Netscape HTTP Cookie File\n\n") + "\n".join(valid_lines) + "\n"
            logger.info("Parsed %d Netscape cookie lines. Key tokens detected: %s", len(valid_lines), list(set(found_tokens)))
            return content

    # --- Mode 3: Semicolon-separated key=value format ---
    cookie_dict = {}
    for item in cleaned_raw.split(";"):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            k_clean = k.strip()
            v_clean = v.strip()
            if k_clean and v_clean:
                cookie_dict[k_clean] = v_clean
                if k_clean in KEY_TOKENS:
                    found_tokens.append(k_clean)

    if cookie_dict:
        content = generate_netscape_cookie_content(cookie_dict)
        logger.info("Parsed %d key-value cookies. Key tokens detected: %s", len(cookie_dict), list(set(found_tokens)))
        return content

    logger.warning("DOUYIN_COOKIES present but could not parse any valid cookie entries.")
    return None


def ensure_douyin_cookie_file(output_dir: Path, force_refresh: bool = False) -> Optional[Path]:
    """
    Ensures a valid Netscape cookie file exists in output_dir ONLY if DOUYIN_COOKIES is provided.
    Does NOT generate fake guest cookies, allowing yt-dlp to run cleanly without cookie flags.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = output_dir / "douyin_cookies.txt"

    # 1. Check if user provided cookies via env
    raw_env_cookies = os.getenv("DOUYIN_COOKIES")
    if raw_env_cookies and raw_env_cookies.strip():
        logger.info("DOUYIN_COOKIES environment variable detected (%d characters). Parsing...", len(raw_env_cookies))
        parsed_content = parse_and_validate_cookies(raw_env_cookies)
        if parsed_content:
            cookie_path.write_text(parsed_content, encoding="utf-8")
            logger.info("Successfully wrote %d bytes to cookie file: %s", cookie_path.stat().st_size, cookie_path)
            return cookie_path
        else:
            logger.warning("Could not parse DOUYIN_COOKIES secret!")

    if cookie_path.exists() and not force_refresh:
        if cookie_path.stat().st_size > 50:
            return cookie_path

    logger.info("No DOUYIN_COOKIES provided; yt-dlp will run cleanly in unauthenticated CLI mode (no cookies).")
    return None
