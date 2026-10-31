import unittest
from src.config_loader import load_config, load_history, VideoMetadata, QualityResult


class TestConfigAndMetadata(unittest.TestCase):

    def test_channel_config_structure(self):
        config = load_config()
        self.assertIn("channel", config)
        self.assertIn("metadata_templates", config)
        self.assertIn("schedule", config)
        self.assertIn("quality_gate", config)
        self.assertIn("seed_categories", config)

        self.assertEqual(config["schedule"]["daily_max_candidates"], 6)
        self.assertEqual(config["schedule"]["daily_publish_count"], 3)
        self.assertEqual(config["quality_gate"]["primary_vision_model"], "gemini-3.1-flash-lite")
        self.assertEqual(config["quality_gate"]["primary_text_model"], "gemini-3.1-flash-lite")
        self.assertGreater(len(config["seed_categories"]), 0)

    def test_models_contracts(self):
        meta = VideoMetadata(
            video_id="123456",
            url="https://www.douyin.com/video/123456",
            title="Test Dance",
            author_name="Dancer A",
            author_id="dancer_a",
            duration=15.5,
        )
        self.assertEqual(meta.video_id, "123456")

        quality = QualityResult(
            is_dance_cover=True,
            has_dancer=True,
            is_safe=True,
            no_blocking_watermark=True,
            overall_pass=True,
            detected_dance="Kpop Choreo",
        )
        self.assertTrue(quality.overall_pass)

    def test_topics_config_structure(self):
        from src.ai_keywords import load_topics_config
        topics = load_topics_config("config/topics.json")
        self.assertIsNotNone(topics)
        self.assertIn("categories", topics)
        self.assertGreater(len(topics["categories"]), 0)

        for cat in topics["categories"]:
            self.assertIn("id", cat)
            self.assertIn("name", cat)
            self.assertIn("douyin_queries", cat)
            self.assertIn("tiktok_hashtags", cat)
            self.assertGreater(len(cat["douyin_queries"]), 0)
            self.assertGreater(len(cat["tiktok_hashtags"]), 0)

    def test_load_topics_config_fallback(self):
        from src.ai_keywords import load_topics_config
        missing = load_topics_config("config/non_existent_topics.json")
        self.assertIsNone(missing)

    def test_update_jina_quota_state(self):
        from src.main import update_jina_quota_state

        # 1. Same/Initial key: deduct from 2,055,014
        hist = {"jina_tokens_remaining": 2055014}
        rem = update_jina_quota_state(hist, "current_key_xyz", 55014)
        self.assertEqual(rem, 2000000)
        self.assertEqual(hist["jina_tokens_remaining"], 2000000)
        self.assertEqual(hist["jina_total_consumed"], 55014)

        # 2. Second run with same key: further deduction
        rem2 = update_jina_quota_state(hist, "current_key_xyz", 100000)
        self.assertEqual(rem2, 1900000)
        self.assertEqual(hist["jina_tokens_remaining"], 1900000)
        self.assertEqual(hist["jina_total_consumed"], 155014)

        # 3. New key detected: resets to 10,000,000 - tokens_used
        rem3 = update_jina_quota_state(hist, "brand_new_key_123", 20000)
        self.assertEqual(rem3, 10_000_000 - 20000)
        self.assertEqual(hist["jina_tokens_remaining"], 9980000)

    def test_youtube_upload_config_structure(self):
        from src.config_loader import load_youtube_upload_config
        yt_config = load_youtube_upload_config()
        self.assertIn("snippet_defaults", yt_config)
        self.assertIn("status_defaults", yt_config)
        self.assertIn("metadata_system_prompt", yt_config)
        self.assertGreater(len(yt_config["metadata_system_prompt"]), 100)
        self.assertEqual(yt_config["snippet_defaults"]["categoryId"], "24")

    def test_search_result_item_contract(self):
        from src.searcher import SearchResultItem, SearchReport
        item = SearchResultItem(url="https://www.douyin.com/video/123", jina_title="Test Title", jina_description="Test Desc")
        self.assertEqual(item.url, "https://www.douyin.com/video/123")
        self.assertEqual(item.jina_title, "Test Title")
        self.assertEqual(item.jina_description, "Test Desc")

        report = SearchReport(discovered_items=[item])
        self.assertEqual(len(report.discovered_items), 1)
        self.assertEqual(report.discovered_urls, ["https://www.douyin.com/video/123"])

    def test_metadata_generator_parsing(self):
        from src.metadata_generator import _parse_ai_response

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
        self.assertEqual(meta.title, "Insane Hip-Hop Choreo #dance #dancecover #shorts")
        self.assertIn("oversized hoodie", meta.description_contextual)
        self.assertIn("#dancover_uni", meta.description_hashtags)
        self.assertIn("hip hop", meta.tags)
        self.assertEqual(meta.pinned_comment, "Rate this performance from 1 to 10! 🔥")

        full_desc = meta.format_full_description(author_name="DancePro", original_url="https://douyin.com/video/123")
        self.assertNotIn("Creator Credit", full_desc)
        self.assertNotIn("Original Video", full_desc)
        self.assertNotIn("🔑", full_desc)
        self.assertNotIn("📌", full_desc)
        self.assertIn("All rights belong to the original creators", full_desc)

    def test_metadata_generator_fallback(self):
        from src.metadata_generator import _fallback_metadata
        fb = _fallback_metadata("Kpop Choreo", jina_title="Original Title")
        self.assertIn("Original Title", fb.title)
        self.assertIn("Kpop Choreo", fb.description_contextual)
        self.assertNotIn("🔥", fb.description_contextual)
        self.assertGreater(len(fb.tags), 0)
        self.assertNotEqual(fb.pinned_comment, "")


if __name__ == "__main__":
    unittest.main()
