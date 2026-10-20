import os
import logging
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)


def send_telegram_message(
    bot_token: Optional[str],
    chat_id: Optional[str],
    text: str,
) -> bool:
    """Sends a text notification message to the Telegram chat/channel."""
    if not bot_token or not chat_id:
        logger.info("[MOCK] Telegram Message: %s", text)
        return True

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True
        logger.warning("Telegram sendMessage returned %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Failed to send Telegram message: %s", e)
    return False


def send_telegram_video_backup(
    bot_token: Optional[str],
    chat_id: Optional[str],
    video_path: str,
    caption: str,
) -> bool:
    """
    Uploads the MP4 video to Telegram as backup.
    If video exceeds 49MB (Telegram Bot API limit), sends message notice instead.
    """
    if not bot_token or not chat_id:
        logger.info("[MOCK] Telegram Video Backup: %s (caption: %s)", video_path, caption)
        return True

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if file_size_mb > 49.0:
        logger.warning("Video file size (%.2fMB) exceeds Telegram Bot 50MB limit; sending caption only.", file_size_mb)
        return send_telegram_message(bot_token, chat_id, f"⚠️ Video size {file_size_mb:.1f}MB exceeds 50MB:\n\n{caption}")

    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    try:
        with open(video_path, "rb") as vf:
            files = {"video": vf}
            data = {
                "chat_id": chat_id,
                "caption": caption[:1024],  # Telegram caption max 1024 chars
                "parse_mode": "HTML",
            }
            logger.info("Uploading video backup to Telegram (%.2fMB)...", file_size_mb)
            resp = requests.post(url, data=data, files=files, timeout=90)
            if resp.status_code == 200:
                logger.info("Successfully uploaded video backup to Telegram.")
                return True
            logger.warning("Telegram sendVideo returned %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Failed uploading video to Telegram: %s", e)

    return False


def send_pipeline_summary(
    bot_token: Optional[str],
    chat_id: Optional[str],
    jina_tokens: int,
    total_scraped: int,
    total_fresh: int,
    total_downloaded: int,
    total_approved: int,
    total_rejected: int,
    today_published: int,
    tomorrow_scheduled: int,
    dry_run: bool = False,
) -> bool:
    """
    Sends an executive summary of the pipeline execution to Telegram.
    Includes Jina API token consumption, scraping count, approval rate, and scheduling stats.
    """
    mode_badge = "🧪 <b>[DRY-RUN - Giả Lập]</b>" if dry_run else "🚀 <b>[PRODUCTION - Đăng Kênh]</b>"

    summary_text = (
        f"📊 <b>DanceCoverUni Pipeline Execution Summary</b>\n"
        f"{mode_badge}\n\n"
        f"🔍 <b>Tìm Kiếm & Cào Dữ Liệu:</b>\n"
        f"• Jina API Tokens: <code>{jina_tokens:,}</code> tokens\n"
        f"• Tổng video đã cào thô: <b>{total_scraped}</b>\n"
        f"• Ứng viên mới (chưa qua xử lý): <b>{total_fresh}</b>\n\n"
        f"🎯 <b>Tải & Kiểm Định AI (Gemini 3.1):</b>\n"
        f"• Tải thành công: <b>{total_downloaded}</b>\n"
        f"• Hợp lệ (Approved): <b>{total_approved}</b>\n"
        f"• Từ chối (Rejected): <b>{total_rejected}</b>\n\n"
        f"📅 <b>Lập Lịch Phân Phối YouTube:</b>\n"
        f"• Đăng hôm nay (Public/Delays): <b>{today_published}</b> video\n"
        f"• Lập lịch ngày mai: <b>{tomorrow_scheduled}</b> video\n\n"
        f"<i>Pipeline hoàn thành chu kỳ tự động thành công.</i>"
    )

    return send_telegram_message(bot_token, chat_id, summary_text)

