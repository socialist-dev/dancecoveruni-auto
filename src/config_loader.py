import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "channel_config.json"
HISTORY_PATH = ROOT_DIR / "data" / "history.json"
YOUTUBE_UPLOAD_CONFIG_PATH = ROOT_DIR / "config" / "youtube_upload.json"


class VideoMetadata(BaseModel):
    video_id: str
    url: str
    title: str = ""
    author_name: str = "Unknown"
    author_id: str = "Unknown"
    duration: float = 0.0
    local_filepath: Optional[str] = None
    detected_dance: str = "Dance Cover"


class QualityResult(BaseModel):
    is_dance_cover: bool = False
    has_dancer: bool = False
    is_safe: bool = True
    no_blocking_watermark: bool = True
    overall_pass: bool = False
    detected_dance: str = "Dance Cover"
    rejection_reason: str = ""
    frame_paths: List[str] = Field(default_factory=list)


class EnvSecrets(BaseModel):
    gemini_api_key: Optional[str] = None
    jina_api_key: Optional[str] = None
    firecrawl_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    youtube_client_id: Optional[str] = None
    youtube_client_secret: Optional[str] = None
    youtube_refresh_token: Optional[str] = None


def load_config() -> Dict[str, Any]:
    """Loads channel configuration from config/channel_config.json."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found at: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_env_secrets() -> EnvSecrets:
    """Loads secrets injected via environment variables (GitHub Actions Secrets)."""
    return EnvSecrets(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        jina_api_key=os.getenv("JINA_API_KEY"),
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        youtube_client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        youtube_client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        youtube_refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
    )


def load_history() -> Dict[str, Any]:
    """Loads deduplication history from data/history.json."""
    if not HISTORY_PATH.exists():
        return {"last_updated": None, "processed_urls": [], "uploaded_videos": []}
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_updated": None, "processed_urls": [], "uploaded_videos": []}


def save_history(history_data: Dict[str, Any]) -> None:
    """Saves updated history to data/history.json atomically."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = HISTORY_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)
    temp_path.replace(HISTORY_PATH)


def load_youtube_upload_config() -> Dict[str, Any]:
    """Loads YouTube upload configuration from config/youtube_upload.json."""
    if not YOUTUBE_UPLOAD_CONFIG_PATH.exists():
        return {
            "snippet_defaults": {"categoryId": "24", "defaultLanguage": "vi"},
            "status_defaults": {"selfDeclaredMadeForKids": False},
            "metadata_system_prompt": "",
        }
    with open(YOUTUBE_UPLOAD_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
