import os
import re
import logging
from pathlib import Path
from typing import Optional
import requests
import yt_dlp
from .config_loader import VideoMetadata
from .cookie_manager import ensure_douyin_cookie_file

logger = logging.getLogger(__name__)

VALID_DOUYIN_PATTERN = re.compile(r"^https://www\.douyin\.com/video/(\d+)$")
VALID_TIKTOK_PATTERN = re.compile(r"^https://www\.tiktok\.com/@[^/]+/video/(\d+)$")


def is_valid_download_url(url: str) -> bool:
    """Checks whether the URL is in a strict canonical video format."""
    if not url:
        return False
    return bool(VALID_DOUYIN_PATTERN.match(url) or VALID_TIKTOK_PATTERN.match(url))


def extract_video_id(url: str) -> Optional[str]:
    """Extracts numeric video ID from canonical Douyin/TikTok URL."""
    m = VALID_DOUYIN_PATTERN.match(url) or VALID_TIKTOK_PATTERN.match(url)
    return m.group(1) if m else None


def download_with_ytdlp(url: str, output_dir: Path, cookie_file: Optional[Path]) -> Optional[VideoMetadata]:
    """Downloads video using yt-dlp with cookiefile and browser headers."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        },
    }

    if cookie_file and cookie_file.exists():
        ydl_opts["cookiefile"] = str(cookie_file)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        logger.info("yt-dlp attempting download: %s (cookiefile=%s)", url, bool(cookie_file))
        info = ydl.extract_info(url, download=True)
        if not info:
            return None

        video_id = str(info.get("id", "video"))
        title = str(info.get("title", ""))
        uploader = str(info.get("uploader") or info.get("channel") or "Douyin Creator")
        uploader_id = str(info.get("uploader_id") or info.get("channel_id") or "douyin")
        duration = float(info.get("duration") or 0.0)

        expected_file = output_dir / f"{video_id}.mp4"
        if not expected_file.exists():
            for f in output_dir.glob(f"{video_id}.*"):
                if f.is_file() and f.suffix in [".mp4", ".webm", ".mkv"]:
                    expected_file = f
                    break

        if not expected_file.exists():
            logger.warning("Downloaded media file not found on disk for ID: %s", video_id)
            return None

        return VideoMetadata(
            video_id=video_id,
            url=url,
            title=title,
            author_name=uploader,
            author_id=uploader_id,
            duration=duration,
            local_filepath=str(expected_file.resolve()),
        )


def download_with_direct_douyin_api(url: str, output_dir: Path) -> Optional[VideoMetadata]:
    """
    Fallback method: attempts to fetch video metadata and play URL directly from Douyin web API.
    Used only if yt-dlp fails after retries.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Referer": "https://www.douyin.com/",
    }

    try:
        logger.info("Attempting direct API fallback for Douyin ID %s...", video_id)
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            item_list = data.get("item_list", [])
            if item_list:
                item = item_list[0]
                title = item.get("desc", "")
                author = item.get("author", {}).get("nickname", "Douyin Creator")
                author_id = item.get("author", {}).get("unique_id") or item.get("author", {}).get("short_id", "douyin")
                duration = float(item.get("duration", 0)) / 1000.0

                video_info = item.get("video", {})
                play_urls = video_info.get("play_addr", {}).get("url_list", [])
                if play_urls:
                    # Replace 'playwm' with 'play' to get watermark-free stream if possible
                    raw_stream_url = play_urls[0].replace("playwm", "play")
                    dest_file = output_dir / f"{video_id}.mp4"

                    stream_resp = requests.get(raw_stream_url, headers=headers, stream=True, timeout=25)
                    if stream_resp.status_code == 200:
                        with open(dest_file, "wb") as f:
                            for chunk in stream_resp.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                        if dest_file.exists() and dest_file.stat().st_size > 10000:
                            logger.info("Successfully downloaded video via direct Douyin API: %s", dest_file)
                            return VideoMetadata(
                                video_id=video_id,
                                url=url,
                                title=title,
                                author_name=author,
                                author_id=author_id,
                                duration=duration,
                                local_filepath=str(dest_file.resolve()),
                            )
    except Exception as e:
        logger.debug("Direct API fallback failed for %s: %s", url, e)

    return None


def download_video(url: str, output_dir: Path, max_retries: int = 2) -> Optional[VideoMetadata]:
    """
    Downloads video using yt-dlp with automatic guest cookie management and retry logic.
    Falls back to direct API if yt-dlp cannot extract the stream.
    """
    if not is_valid_download_url(url):
        logger.warning("Rejected non-canonical video URL: %s", url)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    cookie_file = ensure_douyin_cookie_file(output_dir)

    for attempt in range(1, max_retries + 1):
        try:
            result = download_with_ytdlp(url, output_dir, cookie_file)
            if result:
                return result
        except Exception as e:
            err_msg = str(e)
            logger.warning("yt-dlp attempt %d/%d failed for %s: %s", attempt, max_retries, url, err_msg)
            if "cookies" in err_msg.lower() or "403" in err_msg or "login" in err_msg.lower():
                logger.info("Cookie issue detected; refreshing Douyin guest cookies for next attempt...")
                cookie_file = ensure_douyin_cookie_file(output_dir, force_refresh=True)

    # Secondary layer fallback
    logger.info("yt-dlp failed after %d attempts; trying direct API fallback for %s...", max_retries, url)
    api_result = download_with_direct_douyin_api(url, output_dir)
    if api_result:
        return api_result

    logger.warning("All download methods failed for URL: %s", url)
    return None
