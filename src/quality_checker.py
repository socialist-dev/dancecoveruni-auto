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
    Returns list of paths to extracted image files.
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
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
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
    model_name: str = "gemini-2.5-flash",
    sleep_seconds: int = 3,
    sample_count: int = 3,
) -> QualityResult:
    """
    Extracts video frames and sends them to Gemini Vision for quality evaluation.
    Enforces a sleep delay to protect against Gemini RPM/RPD limits.
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
        )

    temp_frames_dir = Path(video_path).parent / f"frames_{Path(video_path).stem}"
    frame_files = extract_frames_with_ffmpeg(video_path, temp_frames_dir, duration, sample_count)

    if not frame_files:
        logger.warning("No frames could be extracted from %s; failing check.", video_path)
        return QualityResult(overall_pass=False, rejection_reason="Failed to extract frames with ffmpeg")

    try:
        from google import genai
        from google.genai import types
        from PIL import Image

        client = genai.Client(api_key=gemini_api_key)
        images = [Image.open(f) for f in frame_files]

        contents = [prompt] + images

        logger.info("Sending %d frames to Gemini Vision (%s) for quality check...", len(images), model_name)
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
        )

        # Enforce rate limit pause
        if sleep_seconds > 0:
            logger.info("Rate limit safety: sleeping for %d seconds...", sleep_seconds)
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
        result = QualityResult(
            is_dance_cover=data.get("is_dance_cover", False),
            has_dancer=data.get("has_dancer", False),
            is_safe=data.get("is_safe", True),
            no_blocking_watermark=data.get("no_blocking_watermark", True),
            overall_pass=data.get("overall_pass", False),
            detected_dance=data.get("detected_dance") or "Dance Cover",
            rejection_reason=data.get("rejection_reason", ""),
        )
        logger.info(
            "Gemini Quality Verdict: overall_pass=%s, detected_dance='%s', reason='%s'",
            result.overall_pass,
            result.detected_dance,
            result.rejection_reason,
        )
        return result
    except Exception as e:
        logger.error("Error during Gemini Vision quality check: %s", e)
        # Sleep even on error to avoid hammering API
        time.sleep(sleep_seconds)
        return QualityResult(overall_pass=False, rejection_reason=f"Gemini inspection error: {e}")
    finally:
        # Clean up temporary frame files
        for f in frame_files:
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            temp_frames_dir.rmdir()
        except OSError:
            pass
