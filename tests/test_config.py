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
    assert config["quality_gate"]["primary_text_model"] == "gemini-3.1-flash-lite"
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


def test_topics_config_structure():
    from src.ai_keywords import load_topics_config
    topics = load_topics_config("config/topics.json")
    assert topics is not None
    assert "categories" in topics
    assert len(topics["categories"]) > 0

    for cat in topics["categories"]:
        assert "id" in cat
        assert "name" in cat
        assert "douyin_queries" in cat
        assert "tiktok_hashtags" in cat
        assert len(cat["douyin_queries"]) > 0
        assert len(cat["tiktok_hashtags"]) > 0


def test_load_topics_config_fallback():
    from src.ai_keywords import load_topics_config
    missing = load_topics_config("config/non_existent_topics.json")
    assert missing is None


def test_update_jina_quota_state():
    from src.main import update_jina_quota_state

    # 1. Same/Initial key: deduct from 2,055,014
    hist = {"jina_tokens_remaining": 2055014}
    rem = update_jina_quota_state(hist, "current_key_xyz", 55014)
    assert rem == 2000000
    assert hist["jina_tokens_remaining"] == 2000000
    assert hist["jina_total_consumed"] == 55014

    # 2. Second run with same key: further deduction
    rem2 = update_jina_quota_state(hist, "current_key_xyz", 100000)
    assert rem2 == 1900000
    assert hist["jina_tokens_remaining"] == 1900000
    assert hist["jina_total_consumed"] == 155014

    # 3. New key detected: resets to 10,000,000 - tokens_used
    rem3 = update_jina_quota_state(hist, "brand_new_key_123", 20000)
    assert rem3 == 10_000_000 - 20000
    assert hist["jina_tokens_remaining"] == 9980000


def test_youtube_upload_config_structure():
    from src.config_loader import load_youtube_upload_config
    yt_config = load_youtube_upload_config()
    assert "snippet_defaults" in yt_config
    assert "status_defaults" in yt_config
    assert "metadata_system_prompt" in yt_config
    assert len(yt_config["metadata_system_prompt"]) > 100
    assert yt_config["snippet_defaults"]["categoryId"] == "24"


def test_search_result_item_contract():
    from src.searcher import SearchResultItem, SearchReport
    item = SearchResultItem(url="https://www.douyin.com/video/123", jina_title="Test Title", jina_description="Test Desc")
    assert item.url == "https://www.douyin.com/video/123"
    assert item.jina_title == "Test Title"
    assert item.jina_description == "Test Desc"

    report = SearchReport(discovered_items=[item])
    assert len(report.discovered_items) == 1
    assert report.discovered_urls == ["https://www.douyin.com/video/123"]


def test_metadata_generator_parsing():
    from src.metadata_generator import _parse_ai_response, _fallback_metadata, YouTubeMetadata

    sample_ai_json = {
        "title": "Insane Hip-Hop Choreo #dance #dancecover #shorts",
        "description": {
            "contextual_summary": "Dancer in \"oversized hoodie\" executing sharp popping.",
            "thematic_seo": "Viral rhythm breakdown and stage presence.",
            "hashtags": "#hiphop #streetdance #dancover_uni",
            "keyword_cloud": "hiphop, popping, urban dance"
        },
        "tags": "dance cover, hip hop, popping, street dance",
        "pinned_comment": "Rate this performance from 1 to 10! 🔥"
    }

    meta = _parse_ai_response(sample_ai_json)
    assert meta.title == "Insane Hip-Hop Choreo #dance #dancecover #shorts"
    assert "oversized hoodie" in meta.description_contextual
    assert "#dancover_uni" in meta.description_hashtags
    assert "hip hop" in meta.tags
    assert meta.pinned_comment == "Rate this performance from 1 to 10! 🔥"

    full_desc = meta.format_full_description(author_name="DancePro", original_url="https://douyin.com/video/123")
    assert "Creator Credit: DancePro" in full_desc
    assert "Original Video: https://douyin.com/video/123" in full_desc
    assert "All rights belong to the original creators" in full_desc


def test_metadata_generator_fallback():
    from src.metadata_generator import _fallback_metadata
    fb = _fallback_metadata("Kpop Choreo", jina_title="Original Title")
    assert "Original Title" in fb.title
    assert "Kpop Choreo" in fb.description_contextual
    assert len(fb.tags) > 0
    assert fb.pinned_comment != ""


