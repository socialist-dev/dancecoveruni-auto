import unittest
from src.searcher import canonicalize_url, extract_video_urls_from_text
from src.config_loader import QualityResult, load_channel_strategy
from src.quality_checker import inspect_video_quality
from src.ai_keywords import generate_chinese_keywords_with_gemini


class TestQualityCheckerAndStrategy(unittest.TestCase):
    def test_canonicalize_url(self):
        # Valid Douyin with query param
        self.assertEqual(
            canonicalize_url("https://www.douyin.com/video/7391234567890123456?modal_id=123"),
            "https://www.douyin.com/video/7391234567890123456",
        )
        # Douyin URL with trailing characters: dots, comma, ellipsis, slash
        self.assertEqual(
            canonicalize_url("https://www.douyin.com/video/7391234567890123456..."),
            "https://www.douyin.com/video/7391234567890123456",
        )
        self.assertEqual(
            canonicalize_url("https://www.douyin.com/video/7391234567890123456,"),
            "https://www.douyin.com/video/7391234567890123456",
        )
        self.assertEqual(
            canonicalize_url("https://www.douyin.com/video/7391234567890123456."),
            "https://www.douyin.com/video/7391234567890123456",
        )
        self.assertEqual(
            canonicalize_url("https://www.douyin.com/video/7391234567890123456/"),
            "https://www.douyin.com/video/7391234567890123456",
        )

        # Non-video link rejected
        self.assertIsNone(canonicalize_url("https://www.douyin.com/user/MS4wLjABAAAA"))
        self.assertIsNone(canonicalize_url("https://www.douyin.com/search/dance"))

        # Valid TikTok
        self.assertEqual(
            canonicalize_url("https://www.tiktok.com/@bestdancer/video/7123456789012345678?is_from_webapp=1"),
            "https://www.tiktok.com/@bestdancer/video/7123456789012345678",
        )
        self.assertEqual(
            canonicalize_url("https://www.tiktok.com/@bestdancer/video/7123456789012345678..."),
            "https://www.tiktok.com/@bestdancer/video/7123456789012345678",
        )

    def test_extract_video_urls_from_text(self):
        text_sample = """
        Here are the top results from the query:
        1. Check out https://www.douyin.com/video/7391234567890123456 for great choreo.
        2. TikTok link: https://www.tiktok.com/@bestdancer/video/7123456789012345678
        3. Duplicate: https://www.douyin.com/video/7391234567890123456
        4. Junk link: https://www.douyin.com/user/12345
        """
        urls = extract_video_urls_from_text(text_sample)
        self.assertEqual(len(urls), 2)
        self.assertIn("https://www.douyin.com/video/7391234567890123456", urls)
        self.assertIn("https://www.tiktok.com/@bestdancer/video/7123456789012345678", urls)

    def test_load_channel_strategy(self):
        strategy = load_channel_strategy()
        self.assertIn("channel_persona", strategy)
        self.assertIn("aesthetic_standards", strategy)
        self.assertIn("viral_scoring_rubric", strategy)
        self.assertEqual(strategy["viral_scoring_rubric"]["min_overall_score"], 7.0)

    def test_quality_result_viral_scoring(self):
        res = QualityResult(
            is_dance_cover=True,
            has_dancer=True,
            is_safe=True,
            no_blocking_watermark=True,
            overall_pass=True,
            detected_dance="Kpop Jazz",
            outfit_score=9,
            setting_score=8,
            dance_score=9,
            viral_score=8.7,
            aesthetic_notes="Stylish outfit, modern studio",
        )
        self.assertTrue(res.overall_pass)
        self.assertEqual(res.viral_score, 8.7)
        self.assertEqual(res.outfit_score, 9)

    def test_inspect_video_quality_mock_mode(self):
        res = inspect_video_quality(
            video_path="dummy.mp4",
            duration=15.0,
            gemini_api_key=None,
            prompt="test prompt",
        )
        self.assertTrue(res.overall_pass)
        self.assertGreaterEqual(res.viral_score, 7.0)
        self.assertGreaterEqual(res.outfit_score, 5)

    def test_ai_keywords_fallback_contains_strategy_modifiers(self):
        kws = generate_chinese_keywords_with_gemini(None, ["Kpop dance"])
        self.assertGreater(len(kws), 0)
        # Check that multidimensional queries are present
        self.assertTrue(any("练功房" in k or "卡点" in k or "热舞" in k for k in kws))


if __name__ == "__main__":
    unittest.main()
