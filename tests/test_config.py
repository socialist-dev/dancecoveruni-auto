import pytest
from src.config_loader import load_config, load_history, VideoMetadata, QualityResult


def test_channel_config_structure():
    config = load_config()
    assert "channel" in config
    assert "metadata_templates" in config
    assert "schedule" in config
    assert "quality_gate" in config
    assert "seed_categories" in config

    assert config["schedule"]["daily_max_candidates"] == 6
    assert config["schedule"]["daily_publish_count"] == 3
    assert config["quality_gate"]["primary_vision_model"] == "gemini-3.1-flash-lite"
    assert config["quality_gate"]["primary_text_model"] == "gemma-4-31b"
    assert len(config["seed_categories"]) > 0


def test_models_contracts():
    meta = VideoMetadata(
        video_id="123456",
        url="https://www.douyin.com/video/123456",
        title="Test Dance",
        author_name="Dancer A",
        author_id="dancer_a",
        duration=15.5,
    )
    assert meta.video_id == "123456"

    quality = QualityResult(
        is_dance_cover=True,
        has_dancer=True,
        is_safe=True,
        no_blocking_watermark=True,
        overall_pass=True,
        detected_dance="Kpop Choreo",
    )
    assert quality.overall_pass is True
