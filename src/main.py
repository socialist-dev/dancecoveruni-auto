import os
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

from .config_loader import (
    load_config,
    load_env_secrets,
    load_history,
    save_history,
    VideoMetadata,
)
from .ai_keywords import get_search_keywords
from .searcher import discover_video_urls
from .downloader import download_video
from .quality_checker import inspect_video_quality
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


def run_pipeline():
    args = parse_args()
    logger.info("Starting Dance Cover Universe Pipeline (dry_run=%s)", args.dry_run)

    config = load_config()
    secrets = load_env_secrets()
    history = load_history()

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
    candidate_urls, search_report = discover_video_urls(
        keywords=keywords,
        processed_urls=processed_urls,
        jina_api_key=secrets.jina_api_key,
        firecrawl_api_key=secrets.firecrawl_api_key,
        max_needed=max(60, max_target * 10),
    )

    # Track cumulative Jina token consumption and remaining quota
    jina_used = search_report.jina_tokens_used
    total_consumed = history.get("jina_total_consumed", 0) + jina_used
    history["jina_total_consumed"] = total_consumed
    init_quota = history.get("jina_initial_quota", 10_000_000)
    calc_remaining = max(0, init_quota - total_consumed)
    remaining_tokens = search_report.jina_tokens_remaining if search_report.jina_tokens_remaining is not None else calc_remaining
    history["jina_tokens_remaining"] = remaining_tokens

    if not candidate_urls:
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

    approved_candidates: List[tuple[VideoMetadata, str]] = []
    downloaded_count = 0
    rejected_count = 0

    for url in candidate_urls:
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
            approved_candidates.append((meta, verdict.detected_dance))
        else:
            logger.info("❌ Video rejected: [%s] (Reason: %s)", url, verdict.rejection_reason)
            rejected_count += 1
            try:
                os.remove(meta.local_filepath)
            except OSError:
                pass

    logger.info("Total approved videos ready for distribution: %d", len(approved_candidates))

    # Step 4: Upload & Distribution
    now = datetime.now(timezone.utc)
    uploaded_entries = history.get("uploaded_videos", [])
    today_published = 0
    tomorrow_scheduled = 0

    for idx, (meta, dance_name) in enumerate(approved_candidates):
        is_today = idx < today_count
        if is_today:
            today_published += 1
            delay_hours = config.get("schedule", {}).get("today_publish_delays_hours", [0, 4, 8])
            offset = delay_hours[idx] if idx < len(delay_hours) else 0
            publish_time = None if offset == 0 else (now + timedelta(hours=offset))
        else:
            tomorrow_scheduled += 1
            tomorrow_delays = config.get("schedule", {}).get("tomorrow_schedule_delays_hours", [24, 28, 32])
            t_idx = idx - today_count
            offset = tomorrow_delays[t_idx] if t_idx < len(tomorrow_delays) else 24
            publish_time = now + timedelta(hours=offset)

        title = format_metadata(config["metadata_templates"]["title_template"], meta, dance_name)
        desc = format_metadata(config["metadata_templates"]["description_template"], meta, dance_name)
        tags = config["metadata_templates"].get("tags", [])

        # Send Telegram Backup
        tg_caption = f"📹 <b>New Dance Cover</b>\n\n<b>Title:</b> {title}\n<b>Author:</b> {meta.author_name}\n<b>Schedule:</b> {'Today (Public)' if is_today else f'Tomorrow ({publish_time})'}\n<b>Source:</b> {meta.url}"
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
            category_id=config["channel"].get("category_id", "24"),
            publish_at=publish_time,
            dry_run=args.dry_run,
        )

        if yt_id:
            uploaded_entries.append({
                "youtube_id": yt_id,
                "title": title,
                "douyin_url": meta.url,
                "published_at": publish_time.isoformat() if publish_time else now.isoformat(),
                "status": "scheduled" if publish_time else "public",
                "processed_time": now.isoformat(),
            })

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
        total_fresh=len(candidate_urls),
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
