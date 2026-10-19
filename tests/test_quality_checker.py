from src.searcher import canonicalize_url, extract_video_urls_from_text


def test_canonicalize_url():
    # Valid Douyin
    assert (
        canonicalize_url("https://www.douyin.com/video/7391234567890123456?modal_id=123")
        == "https://www.douyin.com/video/7391234567890123456"
    )
    # Non-video link rejected
    assert canonicalize_url("https://www.douyin.com/user/MS4wLjABAAAA") is None
    assert canonicalize_url("https://www.douyin.com/search/dance") is None

    # Valid TikTok
    assert (
        canonicalize_url("https://www.tiktok.com/@bestdancer/video/7123456789012345678?is_from_webapp=1")
        == "https://www.tiktok.com/@bestdancer/video/7123456789012345678"
    )


def test_extract_video_urls_from_text():
    text_sample = """
    Here are the top results from the query:
    1. Check out https://www.douyin.com/video/7391234567890123456 for great choreo.
    2. TikTok link: https://www.tiktok.com/@bestdancer/video/7123456789012345678
    3. Duplicate: https://www.douyin.com/video/7391234567890123456
    4. Junk link: https://www.douyin.com/user/12345
    """
    urls = extract_video_urls_from_text(text_sample)
    assert len(urls) == 2
    assert "https://www.douyin.com/video/7391234567890123456" in urls
    assert "https://www.tiktok.com/@bestdancer/video/7123456789012345678" in urls
