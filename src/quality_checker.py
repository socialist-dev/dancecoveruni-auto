import os
import json
import time
import subprocess
import logging
from pathlib import Path
from typing import List, Optional
from .config_loader import QualityResult

logger = logging.getLogger(__name__)


def extract_frames_with_ffmpeg(
    video_path: str,
    output_dir: Path,
    duration: float,
    sample_count: int = 3,
) -> List[str]:
    """
    Extracts sample frames from video at distributed timestamps using ffmpeg.
    Frames are scaled to max height 720 to reduce token usage and transfer latency.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: List[str] = []

    if duration <= 1.0:
        timestamps = [0.5]
    else:
        step = duration / (sample_count + 1)
        timestamps = [round(step * (i + 1), 2) for i in range(sample_count)]

    for idx, ts in enumerate(timestamps):
        frame_file = output_dir / f"frame_{idx}_{int(ts*10)}.jpg"
        # Scale down to height 720 keeping aspect ratio to save vision tokens
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-vf", "scale=-2:min(720\\,ih)",
            "-q:v", "3",
            str(frame_file),
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if frame_file.exists():
                frame_paths.append(str(frame_file.resolve()))
        except Exception as e:
            logger.warning("ffmpeg frame extraction failed at %ss: %s", ts, e)

    return frame_paths


def inspect_video_quality(
    video_path: str,
    duration: float,
    gemini_api_key: Optional[str],
    prompt: str,
    candidate_models: Optional[List[str]] = None,
    sleep_seconds: int = 3,
    sample_count: int = 3,
) -> QualityResult:
    """
    Extracts video frames and sends them to Gemini Vision for quality evaluation.
    Tries candidate models sequentially (gemini-3.1-flash-lite -> gemini-3.5-flash-lite).
    """
    if not gemini_api_key:
        logger.info("No GEMINI_API_KEY provided; quality check defaults to PASS (mock).")
        return QualityResult(
            is_dance_cover=True,
            has_dancer=True,
            is_safe=True,
            no_blocking_watermark=True,
            overall_pass=True,
            detected_dance="Dance Cover",
            rejection_reason="",
            outfit_score=8,
            setting_score=8,
            dance_score=9,
            viral_score=8.4,
            aesthetic_notes="Mock aesthetic pass (studio, Y2K outfit)",
        )

    if not candidate_models:
        candidate_models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

    temp_frames_dir = Path(video_path).parent / f"frames_{Path(video_path).stem}"
    frame_files = extract_frames_with_ffmpeg(video_path, temp_frames_dir, duration, sample_count)

    if not frame_files:
        logger.warning("No frames could be extracted from %s; failing check.", video_path)
        return QualityResult(overall_pass=False, rejection_reason="Failed to extract frames with ffmpeg")

    try:
        from google import genai
        from PIL import Image
        from .ai_keywords import filter_available_models

        client = genai.Client(api_key=gemini_api_key)
        images = [Image.open(f) for f in frame_files]
        contents = [prompt] + images

        active_candidates = filter_available_models(client, candidate_models)

        for model_name in active_candidates:
            try:
                logger.info("Sending %d frames to Vision model '%s' for evaluation...", len(images), model_name)
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )

                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                data = json.loads(text)

                outfit_score = int(data.get("outfit_score") or 7)
                setting_score = int(data.get("setting_score") or 7)
                dance_score = int(data.get("dance_score") or 7)
                raw_viral = data.get("viral_score")
                try:
                    viral_score = round(float(raw_viral), 1) if raw_viral is not None else round(outfit_score * 0.35 + setting_score * 0.30 + dance_score * 0.35, 1)
                except (ValueError, TypeError):
                    viral_score = round(outfit_score * 0.35 + setting_score * 0.30 + dance_score * 0.35, 1)

                is_dance_cover = bool(data.get("is_dance_cover", False))
                has_dancer = bool(data.get("has_dancer", False))
                is_safe = bool(data.get("is_safe", True))
                no_blocking_watermark = bool(data.get("no_blocking_watermark", True))
                aesthetic_notes = str(data.get("aesthetic_notes") or "").strip()

                base_pass = is_dance_cover and has_dancer and is_safe and no_blocking_watermark
                score_pass = (viral_score >= 7.0) and (min(outfit_score, setting_score, dance_score) >= 5)
                overall_pass = base_pass and score_pass

                rejection_reason = str(data.get("rejection_reason") or "").strip()
                if base_pass and not score_pass:
                    rejection_reason = (
                        f"Low aesthetic/viral score: {viral_score}/10 (outfit={outfit_score}, setting={setting_score}, dance={dance_score}). "
                        f"Notes: {aesthetic_notes}"
                    )

                result = QualityResult(
                    is_dance_cover=is_dance_cover,
                    has_dancer=has_dancer,
                    is_safe=is_safe,
                    no_blocking_watermark=no_blocking_watermark,
                    overall_pass=overall_pass,
                    detected_dance=data.get("detected_dance") or "Dance Cover",
                    rejection_reason=rejection_reason,
                    frame_paths=frame_files,
                    outfit_score=outfit_score,
                    setting_score=setting_score,
                    dance_score=dance_score,
                    viral_score=viral_score,
                    aesthetic_notes=aesthetic_notes,
                )
                logger.info(
                    "Vision Model '%s' Verdict: overall_pass=%s, viral_score=%.1f (outfit=%d, setting=%d, dance=%d), dance='%s', notes='%s', reason='%s'",
                    model_name,
                    result.overall_pass,
                    result.viral_score,
                    result.outfit_score,
                    result.setting_score,
                    result.dance_score,
                    result.detected_dance,
                    result.aesthetic_notes,
                    result.rejection_reason,
                )
                return result
            except Exception as e:
                logger.warning("Vision model '%s' failed: %s. Trying next candidate...", model_name, e)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

        return QualityResult(
            overall_pass=False,
            rejection_reason="All Gemini Vision candidate models failed.",
            frame_paths=frame_files,
        )
    except Exception as e:
        logger.warning("Quality check encountered error: %s", e)
        return QualityResult(
            overall_pass=False,
            rejection_reason=f"Quality check error: {e}",
            frame_paths=frame_files,
        )
