import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

YOUTUBE_UPLOAD_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_client(
    client_id: Optional[str],
    client_secret: Optional[str],
    refresh_token: Optional[str],
):
    """Initializes and refreshes an authenticated YouTube Data API v3 service."""
    if not (client_id and client_secret and refresh_token):
        return None

    credentials = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=YOUTUBE_UPLOAD_SCOPE,
    )

    credentials.refresh(Request())
    return build("youtube", "v3", credentials=credentials)


def upload_youtube_shorts(
    client_id: Optional[str],
    client_secret: Optional[str],
    refresh_token: Optional[str],
    video_filepath: str,
    title: str,
    description: str,
    tags: List[str],
    category_id: str = "24",
    publish_at: Optional[datetime] = None,
    privacy_status: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """
    Uploads vertical video as YouTube Shorts.
    If privacy_status is provided (e.g. 'private', 'unlisted', 'public'):
      - Sets status.privacyStatus directly.
      - If publish_at is also set AND privacy_status == 'private', schedules publication.
    If privacy_status is None:
      - If publish_at is provided, sets privacyStatus to 'private' and schedules publication.
      - Otherwise, publishes immediately ('public').
    Returns YouTube video ID if successful.
    """
    if dry_run:
        status_info = privacy_status if privacy_status else ("SCHEDULED" if publish_at else "PUBLIC")
        logger.info(
            "[MOCK] YouTube Upload (DRY-RUN): Title='%s', status=%s, publish_at=%s",
            title,
            status_info,
            publish_at.isoformat() if publish_at else "None",
        )
        return "mock_yt_id_12345"

    if not (client_id and client_secret and refresh_token):
        logger.error(
            "Missing required YouTube credentials for production upload! (client_id=%s, client_secret=%s, refresh_token=%s)",
            bool(client_id),
            bool(client_secret),
            bool(refresh_token),
        )
        return None

    try:
        service = get_youtube_client(client_id, client_secret, refresh_token)
        if not service:
            logger.error("Could not initialize YouTube API client.")
            return None

        body: Dict[str, Any] = {
            "snippet": {
                "title": title[:100],  # YouTube title max 100 chars
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": category_id,
                "defaultLanguage": "vi",
            },
            "status": {
                "selfDeclaredMadeForKids": False,
            },
        }

        if privacy_status in ["private", "unlisted", "public"]:
            body["status"]["privacyStatus"] = privacy_status
            if publish_at and privacy_status == "private":
                publish_iso = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                body["status"]["publishAt"] = publish_iso
                logger.info("Scheduling YouTube Shorts (%s) for: %s", privacy_status, publish_iso)
            else:
                logger.info("Setting YouTube Shorts status directly to '%s' (No auto-scheduling)", privacy_status)
        elif publish_at:
            # Scheduled publish requires privacyStatus = 'private' and publishAt in RFC 3339 format
            publish_iso = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = publish_iso
            logger.info("Scheduling YouTube Shorts publish for: %s", publish_iso)
        else:
            body["status"]["privacyStatus"] = "public"
            logger.info("Setting YouTube Shorts to publish IMMEDIATELY (Public)")

        media = MediaFileUpload(
            video_filepath,
            mimetype="video/mp4",
            chunksize=1024 * 1024 * 4,  # 4MB chunks
            resumable=True,
        )

        logger.info("Uploading video to YouTube: %s", video_filepath)
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info("YouTube upload progress: %d%%", int(status.progress() * 100))

        video_id = response.get("id")
        logger.info("Successfully uploaded video to YouTube! URL: https://youtube.com/shorts/%s", video_id)
        return video_id
    except HttpError as e:
        logger.error("YouTube API HttpError during upload: status=%s, details=%s", e.status_code, e.error_details or e.content)
        return None
    except Exception as e:
        logger.error("Failed uploading to YouTube: %s", e)
        return None
