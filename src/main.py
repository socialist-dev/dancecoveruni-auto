import os
import sys
import argparse
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from .config_loader import (
    load_config,
    load_env_secrets,
    load_history,
    save_history,
    load_youtube_upload_config,
    VideoMetadata,
    QualityResult,
)
from .ai_keywords import get_search_keywords
from .searcher import discover_video_urls, SearchResultItem
from .downloader import download_video
from .quality_checker import inspect_video_quality
from .metadata_generator import generate_youtube_metadata, YouTubeMetadata
from .telegram_notifier import send_telegram_message, send_telegram_video_backup, send_pipeline_summary
from .youtube_uploader import upload_youtube_shorts

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dancecoveruni.main")


def parse_args():
    parser = argparse.ArgumentParser(description="Dance Cover Universe YouTube Shorts Automation")
    parser.add_argument("--dry-run", action="store_true", help="Simulate pipeline without actual upload")
    parser.add_argument("--max-candidates", type=int, default=6, help="Target number of approved videos (max 6)")
    parser.add_argument(
        "--privacy-status",
        type=str,
        default="default",
        choices=["default", "private", "unlisted", "public"],
        help="YouTube Shorts privacy status override (default uses normal schedule, private/unlisted skips scheduling)",
    )
    return parser.parse_args()


def format_metadata(template_str: str, meta: VideoMetadata, detected_dance: str) -> str:
    """Replaces placeholders in metadata templates."""
    return template_str.format(
        detected_dance=detected_dance,
        author_name=meta.author_name,
        author_id=meta.author_id,
        original_url=meta.url,
        video_title=meta.title,
    )


def update_jina_quota_state(history: dict, jina_api_key: Optional[str], tokens_used: int) -> int:
    """
    Updates the Jina API quota balance in history state.
    Detects if a new Jina API key is used (via fingerprint) and resets to 10,000,000 tokens.
    Otherwise deducts exact tokens_used from current balance (initial default: 2,055,014).
    Returns the updated remaining token count.
    """
    key_fingerprint = hashlib.sha256(jina_api_key.encode("utf-8")).hexdigest()[:12] if jina_api_key else "none"
    last_fingerprint = history.get("jina_key_fingerprint")

    if last_fingerprint and last_fingerprint != key_fingerprint:
        logger.info("New Jina API key detected (%s -> %s)! Resetting quota to 10,000,000 tokens.", last_fingerprint, key_fingerprint)
        current_balance = 10_000_000
    else:
        current_balance = history.get("jina_tokens_remaining", 2055014)

    history["jina_key_fingerprint"] = key_fingerprint
    updated_remaining = max(0, current_balance - tokens_used)
    history["jina_tokens_remaining"] = updated_remaining
    history["jina_total_consumed"] = history.get("jina_total_consumed", 0) + tokens_used
    return updated_remaining


def run_pipeline():
    args = parse_args()
    logger.info("Starting Dance Cover Universe Pipeline (dry_run=%s)", args.dry_run)

    config = load_config()
    yt_upload_config = load_youtube_upload_config()
    secrets = load_env_secrets()
    history = load_history()

    metadata_system_prompt = yt_upload_config.get("metadata_system_prompt", "")

    processed_urls = set(history.get("processed_urls", []))
    max_target = min(args.max_candidates, config.get("schedule", {}).get("daily_max_candidates", 6))
    today_count = config.get("schedule", {}).get("daily_publish_count", 3)

    q_gate = config.get("quality_gate", {})
    text_models = [q_gate.get("primary_text_model", "gemma-4-31b")] + q_gate.get(
        "fallback_text_models", ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
    )
    vision_models = [q_gate.get("primary_vision_model", "gemini-3.1-flash-lite")] + q_gate.get(
        "fallback_vision_models", ["gemini-3.5-flash-lite"]
    )

    # Step 0: Immediate Telegram Startup Ping to verify connection
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    startup_msg = (
        "🚀 <b>[DanceCoverUni] Khởi động pipeline & Kiểm tra kết nối Telegram thành công!</b>\n\n"
        f"📅 <b>Thời gian:</b> {now_str}\n"
        f"🤖 <b>AI Text Model:</b> {text_models[0]}\n"
        f"👁️ <b>AI Vision Model:</b> {vision_models[0]}\n"
        f"🎯 <b>Chế độ:</b> {'DRY-RUN (Thử nghiệm)' if args.dry_run else 'PRODUCTION (Tự động)'}"
    )
    send_telegram_message(secrets.telegram_bot_token, secrets.telegram_chat_id, startup_msg)

    # Step 1: Obtain keywords
    keywords = get_search_keywords(
        gemini_key=secrets.gemini_api_key,
        telegram_token=secrets.telegram_bot_token,
        seed_categories=config.get("seed_categories", []),
        candidate_models=text_models,
    )
    logger.info("Search keywords: %s", keywords)

    # Step 2: Discover video URLs (Jina Search with X-Respond-With: no-content)
    candidate_items, search_report = discover_video_urls(
        keywords=keywords,
        processed_urls=processed_urls,
        jina_api_key=secrets.jina_api_key,
        firecrawl_api_key=secrets.firecrawl_api_key,
        max_needed=max(60, max_target * 10),
    )

    # Track cumulative Jina token consumption and remaining quota via fingerprint
    remaining_tokens = update_jina_quota_state(history, secrets.jina_api_key, search_report.jina_tokens_used)

    if not candidate_items:
        logger.warning("No new video URLs found. Exiting gracefully.")
        send_pipeline_summary(
            bot_token=secrets.telegram_bot_token,
            chat_id=secrets.telegram_chat_id,
            jina_tokens=search_report.jina_tokens_used,
            total_scraped=search_report.total_scraped,
            total_fresh=0,
            total_downloaded=0,
            total_approved=0,
            total_rejected=0,
            today_published=0,
            tomorrow_scheduled=0,
            jina_tokens_remaining=remaining_tokens,
            dry_run=args.dry_run,
        )
        history["last_updated"] = datetime.now(timezone.utc).isoformat()
        save_history(history)
        return

    # Step 3: Download & Quality Assessment Loop
    download_dir = Path(__file__).resolve().parent.parent / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    approved_candidates: List[tuple[VideoMetadata, str, YouTubeMetadata, QualityResult]] = []
    downloaded_count = 0
    rejected_count = 0

    for item in candidate_items:
        url = item.url
        if len(approved_candidates) >= max_target:
            break

        logger.info("Processing URL (%d/%d approved): [%s]", len(approved_candidates), max_target, url)
        meta = download_video(url, download_dir)

        if not meta or not meta.local_filepath:
            logger.warning("Failed downloading or rejected URL [%s], skipping to next candidate.", url)
            continue

        downloaded_count += 1
        processed_urls.add(url)

        # Quality check with Gemini Vision using multi-model fallback
        verdict = inspect_video_quality(
            video_path=meta.local_filepath,
            duration=meta.duration,
            gemini_api_key=secrets.gemini_api_key,
            prompt=q_gate.get("criteria_prompt", ""),
            candidate_models=vision_models,
            sleep_seconds=q_gate.get("rate_limit_sleep_seconds", 3),
            sample_count=q_gate.get("frame_sample_count", 3),
        )

        if verdict.overall_pass:
            logger.info("✅ Video approved: [%s] (Dance: %s)", url, verdict.detected_dance)
            # Generate SEO-optimized YouTube metadata using preserved frames
            yt_meta = generate_youtube_metadata(
                frame_paths=verdict.frame_paths,
                gemini_api_key=secrets.gemini_api_key,
                system_prompt=metadata_system_prompt,
                detected_dance=verdict.detected_dance,
                jina_title=item.jina_title,
                jina_description=item.jina_description,
                author_name=meta.author_name,
                candidate_models=vision_models,
                sleep_seconds=q_gate.get("rate_limit_sleep_seconds", 3),
            )
            approved_candidates.append((meta, verdict.detected_dance, yt_meta, verdict))
        else:
            logger.info("❌ Video rejected: [%s] (Reason: %s)", url, verdict.rejection_reason)
            rejected_count += 1
            try:
                os.remove(meta.local_filepath)
            except OSError:
                pass

        # Cleanup extracted frames for this candidate
        for f in verdict.frame_paths:
            try:
                os.remove(f)
            except OSError:
                pass
        if verdict.frame_paths:
            try:
                Path(verdict.frame_paths[0]).parent.rmdir()
            except OSError:
                pass

    logger.info("Total approved videos ready for distribution: %d", len(approved_candidates))

    # Step 4: Upload & Distribution
    now = datetime.now(timezone.utc)
    uploaded_entries = history.get("uploaded_videos", [])
    today_published = 0
    tomorrow_scheduled = 0

    custom_privacy = args.privacy_status if args.privacy_status != "default" else None

    for idx, (meta, dance_name, yt_meta, verdict) in enumerate(approved_candidates):
        is_today = idx < today_count
        if custom_privacy in ("private", "unlisted"):
            # When forcing private or unlisted test mode, do not auto-schedule publication
            publish_time = None
            schedule_label = f"Manual ({custom_privacy.upper()})"
            today_published += 1
        elif is_today:
            today_published += 1
            delay_hours = config.get("schedule", {}).get("today_publish_delays_hours", [0, 4, 8])
            offset = delay_hours[idx] if idx < len(delay_hours) else 0
            publish_time = None if offset == 0 else (now + timedelta(hours=offset))
            schedule_label = "Today (Public)" if offset == 0 else f"Today Scheduled (+{offset}h)"
        else:
            tomorrow_scheduled += 1
            tomorrow_delays = config.get("schedule", {}).get("tomorrow_schedule_delays_hours", [24, 28, 32])
            t_idx = idx - today_count
            offset = tomorrow_delays[t_idx] if t_idx < len(tomorrow_delays) else 24
            publish_time = now + timedelta(hours=offset)
            schedule_label = f"Tomorrow ({publish_time.strftime('%Y-%m-%d %H:%M UTC')})"

        # Build YouTube metadata with AI output (fallback to templates if empty)
        title = yt_meta.title[:100] if yt_meta.title else format_metadata(config["metadata_templates"]["title_template"], meta, dance_name)
        desc = yt_meta.format_full_description(meta.author_name, meta.url)
        tags = yt_meta.tags if yt_meta.tags else config["metadata_templates"].get("tags", [])

        # Send Telegram Backup with rich metadata caption
        tags_display = ", ".join(tags[:8]) if tags else "dance cover, shorts"
        pin_display = yt_meta.pinned_comment[:100] if yt_meta.pinned_comment else "Rate this dance cover 1-10! 🔥"
        tg_caption = (
            f"📹 <b>New Dance Cover</b>\n\n"
            f"<b>🎬 Title:</b> {title}\n"
            f"<b>👤 Author:</b> {meta.author_name}\n"
            f"<b>📅 Schedule:</b> {schedule_label}\n"
            f"<b>🔗 Source:</b> {meta.url}\n\n"
            f"<b>🏷️ Tags:</b> {tags_display}\n"
            f"<b>💬 Pin:</b> {pin_display}"
        )
        send_telegram_video_backup(
            bot_token=secrets.telegram_bot_token,
            chat_id=secrets.telegram_chat_id,
            video_path=meta.local_filepath,
            caption=tg_caption,
        )

        # Upload to YouTube
        yt_id = upload_youtube_shorts(
            client_id=secrets.youtube_client_id,
            client_secret=secrets.youtube_client_secret,
            refresh_token=secrets.youtube_refresh_token,
            video_filepath=meta.local_filepath,
            title=title,
            description=desc,
            tags=tags,
            category_id=yt_upload_config.get("snippet_defaults", {}).get("categoryId", config["channel"].get("category_id", "24")),
            publish_at=publish_time,
            privacy_status=custom_privacy,
            dry_run=args.dry_run,
        )

        if yt_id:
            uploaded_status = custom_privacy if custom_privacy else ("scheduled" if publish_time else "public")
            uploaded_entries.append({
                "youtube_id": yt_id,
                "title": title,
                "douyin_url": meta.url,
                "published_at": publish_time.isoformat() if publish_time else now.isoformat(),
                "status": uploaded_status,
                "processed_time": now.isoformat(),
                "viral_score": verdict.viral_score,
                "outfit_score": verdict.outfit_score,
                "setting_score": verdict.setting_score,
                "dance_score": verdict.dance_score,
                "aesthetic_notes": verdict.aesthetic_notes,
            })

            # Send Telegram Success Notification with direct Shorts link
            yt_url = f"https://youtube.com/shorts/{yt_id}"
            success_tg_msg = (
                f"🎉 <b>[DanceCoverUni] Upload YouTube Shorts Thành Công!</b>\n\n"
                f"🎬 <b>Tiêu đề:</b> {title}\n"
                f"👤 <b>Creator:</b> {meta.author_name}\n"
                f"🔒 <b>Trạng thái:</b> <code>{uploaded_status.upper()}</code>\n"
                f"🔗 <b>Xem ngay:</b> {yt_url}\n"
                f"🕒 <b>Lịch đăng:</b> {schedule_label}"
            )
            send_telegram_message(secrets.telegram_bot_token, secrets.telegram_chat_id, success_tg_msg)
        else:
            if not args.dry_run and secrets.youtube_client_id:
                fail_tg_msg = (
                    f"⚠️ <b>[DanceCoverUni] Upload YouTube Shorts Thất Bại!</b>\n\n"
                    f"🎬 <b>Tiêu đề:</b> {title}\n"
                    f"🔗 <b>Nguồn:</b> {meta.url}\n"
                    f"<i>Vui lòng kiểm tra log GitHub Actions để biết chi tiết lỗi (Quota/OAuth).</i>"
                )
                send_telegram_message(secrets.telegram_bot_token, secrets.telegram_chat_id, fail_tg_msg)

        # Remove local file after processing
        try:
            os.remove(meta.local_filepath)
        except OSError:
            pass

    # Send Executive Summary Report to Telegram
    send_pipeline_summary(
        bot_token=secrets.telegram_bot_token,
        chat_id=secrets.telegram_chat_id,
        jina_tokens=search_report.jina_tokens_used,
        total_scraped=search_report.total_scraped,
        total_fresh=len(candidate_items),
        total_downloaded=downloaded_count,
        total_approved=len(approved_candidates),
        total_rejected=rejected_count,
        today_published=today_published,
        tomorrow_scheduled=tomorrow_scheduled,
        jina_tokens_remaining=remaining_tokens,
        dry_run=args.dry_run,
    )

    # Step 5: Save State
    history["last_updated"] = now.isoformat()
    history["processed_urls"] = list(processed_urls)
    history["uploaded_videos"] = uploaded_entries
    save_history(history)
    logger.info("Pipeline execution completed successfully. State saved.")


if __name__ == "__main__":
    run_pipeline()
