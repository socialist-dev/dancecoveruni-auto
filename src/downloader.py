import os
import re
import logging
from pathlib import Path
from typing import Optional
import yt_dlp
from .config_loader import VideoMetadata

logger = logging.getLogger(__name__)

VALID_DOUYIN_PATTERN = re.compile(r"^https://www\.douyin\.com/video/\d+$")
VALID_TIKTOK_PATTERN = re.compile(r"^https://www\.tiktok\.com/@[^/]+/video/\d+$")


def is_valid_download_url(url: str) -> bool:
    """Checks whether the URL is in a strict canonical video format accepted by yt-dlp."""
    if not url:
        return False
    return bool(VALID_DOUYIN_PATTERN.match(url) or VALID_TIKTOK_PATTERN.match(url))


def download_video(url: str, output_dir: Path) -> Optional[VideoMetadata]:
    """
    Downloads video using yt-dlp to output_dir and extracts metadata.
    Rejects malformed URLs and handles Douyin scrape blocks gracefully.
    """
    if not is_valid_download_url(url):
        logger.warning("Rejected non-canonical video URL: %s", url)
        return None

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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("yt-dlp downloading: %s", url)
            info = ydl.extract_info(url, download=True)
            if not info:
                logger.warning("yt-dlp returned empty info for %s", url)
                return None

            video_id = str(info.get("id", "video"))
            title = str(info.get("title", ""))
            uploader = str(info.get("uploader") or info.get("channel") or "Douyin Creator")
            uploader_id = str(info.get("uploader_id") or info.get("channel_id") or "douyin")
            duration = float(info.get("duration") or 0.0)

            # Locate downloaded file
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
    except Exception as e:
        logger.warning("yt-dlp failed downloading %s: %s", url, e)
        return None
