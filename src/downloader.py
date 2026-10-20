import os
import re
import logging
from pathlib import Path
from typing import Optional
import requests
import subprocess
import yt_dlp
from .config_loader import VideoMetadata
from .cookie_manager import ensure_douyin_cookie_file

logger = logging.getLogger(__name__)

VALID_DOUYIN_PATTERN = re.compile(r"^https://(?:www\.)?douyin\.com/video/(\d{15,25})$")
VALID_TIKTOK_PATTERN = re.compile(r"^https://(?:www\.)?tiktok\.com/@[^/\s?#]+/video/(\d{15,25})$")


def sanitize_url(url: str) -> str:
    """Strips trailing punctuation, query strings, and whitespace, recovering canonical URL."""
    if not url:
        return ""
    cleaned = url.strip().rstrip(".,:;…!?'\"/) \t\n")
    m = re.search(r"douyin\.com/video/(\d{15,25})", cleaned)
    if m:
        return f"https://www.douyin.com/video/{m.group(1)}"
    m_tk = re.search(r"tiktok\.com/(@[^/\s?#]+/video/(\d{15,25}))", cleaned)
    if m_tk:
        return f"https://www.tiktok.com/{m_tk.group(1)}"
    return cleaned


def is_valid_download_url(url: str) -> bool:
    """Checks whether the URL is in a strict canonical video format."""
    clean = sanitize_url(url)
    return bool(VALID_DOUYIN_PATTERN.match(clean) or VALID_TIKTOK_PATTERN.match(clean))


def extract_video_id(url: str) -> Optional[str]:
    """Extracts numeric video ID from canonical Douyin/TikTok URL."""
    clean = sanitize_url(url)
    m_dy = VALID_DOUYIN_PATTERN.match(clean)
    if m_dy:
        return m_dy.group(1)
    m_tk = VALID_TIKTOK_PATTERN.match(clean)
    if m_tk:
        return m_tk.group(1)
    return None


def get_video_duration(file_path: Path) -> float:
    """Extracts exact media duration using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return round(float(res.stdout.strip()), 2)
    except Exception as e:
        logger.debug("ffprobe failed for %s: %s", file_path, e)
    return 30.0


def run_ytdlp_cli(url: str, output_dir: Path, cookie_file: Optional[Path] = None) -> Optional[VideoMetadata]:
    """
    [Layer 1 & 2] Executes yt-dlp CLI directly via subprocess, matching local CLI behavior.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    video_id = extract_video_id(url) or "video"
    outtmpl = str(output_dir / f"{video_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "--socket-timeout", "30",
        "--merge-output-format", "mp4",
        "-o", outtmpl,
    ]

    if cookie_file and cookie_file.exists():
        cmd.extend(["--cookies", str(cookie_file.resolve())])

    cmd.append(url)

    logger.info("Executing CLI yt-dlp for URL [%s] (with_cookie=%s)...", url, bool(cookie_file))
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)

        # Look for downloaded file
        expected_file = output_dir / f"{video_id}.mp4"
        if not expected_file.exists():
            for f in output_dir.glob(f"{video_id}.*"):
                if f.is_file() and f.suffix in [".mp4", ".webm", ".mkv"]:
                    expected_file = f
                    break

        if proc.returncode == 0 and expected_file and expected_file.exists() and expected_file.stat().st_size > 10000:
            duration = get_video_duration(expected_file)
            logger.info("✅ CLI yt-dlp successfully downloaded [%s] -> %s (%d bytes, %.1fs)", url, expected_file.name, expected_file.stat().st_size, duration)
            return VideoMetadata(
                video_id=video_id,
                url=url,
                title="Trending Dance Cover",
                author_name="Douyin Creator",
                author_id="douyin",
                duration=duration,
                local_filepath=str(expected_file.resolve()),
            )
        else:
            err_output = (proc.stderr or proc.stdout or "").strip()
            err_lines = [l for l in err_output.splitlines() if "ERROR" in l or "warning" in l.lower()]
            summary_msg = "; ".join(err_lines[:2]) if err_lines else err_output[-180:]
            logger.warning("CLI yt-dlp failed for URL [%s] | Exit code: %d | Detail: %s", url, proc.returncode, summary_msg)
    except Exception as e:
        logger.warning("CLI yt-dlp execution error for URL [%s]: %s", url, e)

    return None


def download_with_direct_douyin_api(url: str, output_dir: Path) -> Optional[VideoMetadata]:
    """
    [Layer 3] Direct Stream Gateway fallback:
    Attempts download via TikWM public gateway (supports both Douyin and TikTok watermark-free)
    and Douyin Aweme detail endpoint.
    """
    video_id = extract_video_id(url) or "video"
    dest_file = output_dir / f"{video_id}.mp4"

    # 1. Gateway Attempt: TikWM API
    tikwm_endpoint = f"https://www.tikwm.com/api/?url={url}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }
    try:
        logger.info("Attempting Gateway download for URL [%s] via TikWM API...", url)
        resp = requests.get(tikwm_endpoint, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 and "data" in data:
                v_data = data["data"]
                stream_url = v_data.get("play") or v_data.get("wmplay")
                if stream_url:
                    stream_resp = requests.get(stream_url, headers=headers, stream=True, timeout=30)
                    if stream_resp.status_code == 200:
                        with open(dest_file, "wb") as f:
                            for chunk in stream_resp.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                        if dest_file.exists() and dest_file.stat().st_size > 10000:
                            duration = float(v_data.get("duration") or get_video_duration(dest_file))
                            title = v_data.get("title") or "Trending Dance Cover"
                            author = v_data.get("author", {}).get("nickname") or "Dance Creator"
                            author_id = v_data.get("author", {}).get("unique_id") or "creator"
                            logger.info("✅ Gateway API successfully downloaded [%s] -> %s (%d bytes)", url, dest_file.name, dest_file.stat().st_size)
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
        logger.debug("Gateway API failed for URL [%s]: %s", url, e)

    # 2. Douyin Aweme detail endpoint fallback
    if "douyin.com" in url:
        aweme_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
        douyin_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.douyin.com/",
        }
        cookie_val = os.getenv("DOUYIN_COOKIES", "")
        if cookie_val:
            douyin_headers["Cookie"] = cookie_val.replace("\n", " ").strip()
        try:
            logger.info("Attempting Douyin Aweme detail endpoint for ID [%s]...", video_id)
            d_resp = requests.get(aweme_url, headers=douyin_headers, timeout=12)
            if d_resp.status_code == 200:
                d_json = d_resp.json()
                item = d_json.get("aweme_detail", {})
                play_urls = item.get("video", {}).get("play_addr", {}).get("url_list", [])
                if play_urls:
                    raw_stream = play_urls[0].replace("playwm", "play")
                    s_resp = requests.get(raw_stream, headers=douyin_headers, stream=True, timeout=25)
                    if s_resp.status_code == 200:
                        with open(dest_file, "wb") as f:
                            for chunk in s_resp.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                        if dest_file.exists() and dest_file.stat().st_size > 10000:
                            duration = float(item.get("duration", 0)) / 1000.0 or get_video_duration(dest_file)
                            return VideoMetadata(
                                video_id=video_id,
                                url=url,
                                title=item.get("desc", "Dance Cover"),
                                author_name=item.get("author", {}).get("nickname", "Douyin Creator"),
                                author_id=item.get("author", {}).get("unique_id", "douyin"),
                                duration=duration,
                                local_filepath=str(dest_file.resolve()),
                            )
        except Exception as e:
            logger.debug("Douyin Aweme detail API failed for ID [%s]: %s", video_id, e)

    return None


def download_video(url: str, output_dir: Path, max_retries: int = 2) -> Optional[VideoMetadata]:
    """
    3-Layer Resilient Download Architecture:
    - Layer 1: Pure CLI yt-dlp WITHOUT cookies (100% equivalent to your local machine command).
    - Layer 2: CLI yt-dlp WITH true DOUYIN_COOKIES (if provided).
    - Layer 3: Direct API / TikWM Stream Gateway (high-speed datacenter bypass).
    """
    clean_url = sanitize_url(url)
    if not is_valid_download_url(clean_url):
        logger.warning("Rejected non-canonical video URL [%s]", url)
        return None
    url = clean_url

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Layer 1: CLI yt-dlp without cookies (local machine mode) ---
    logger.info("▶ [Layer 1] Trying pure CLI yt-dlp (no cookies, default CLI mode) for URL [%s]...", url)
    res_layer1 = run_ytdlp_cli(url, output_dir, cookie_file=None)
    if res_layer1:
        return res_layer1

    # --- Layer 2: CLI yt-dlp with true DOUYIN_COOKIES (if secret exists) ---
    cookie_file = ensure_douyin_cookie_file(output_dir)
    if cookie_file and cookie_file.exists():
        logger.info("▶ [Layer 2] Trying CLI yt-dlp with DOUYIN_COOKIES for URL [%s]...", url)
        res_layer2 = run_ytdlp_cli(url, output_dir, cookie_file=cookie_file)
        if res_layer2:
            return res_layer2

    # --- Layer 3: Direct Stream Gateway / TikWM API fallback ---
    logger.info("▶ [Layer 3] Trying Direct Stream Gateway fallback for URL [%s]...", url)
    res_layer3 = download_with_direct_douyin_api(url, output_dir)
    if res_layer3:
        return res_layer3

    logger.warning("❌ All 3 download layers failed for URL [%s]", url)
    return None
