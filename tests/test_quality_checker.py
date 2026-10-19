from src.searcher import extract_video_urls


def test_extract_video_urls():
    text_sample = """
    Here are the top results from the query:
    1. Check out https://www.douyin.com/video/7391234567890123456 for great choreo.
    2. Another mobile short link: https://v.douyin.com/iRoAbCd/
    3. TikTok link: https://www.tiktok.com/@bestdancer/video/7123456789012345678
    4. Duplicate: https://www.douyin.com/video/7391234567890123456
    """
    urls = extract_video_urls(text_sample)
    assert len(urls) == 3
    assert "https://www.douyin.com/video/7391234567890123456" in urls
    assert "https://v.douyin.com/iRoAbCd" in urls
    assert "https://www.tiktok.com/@bestdancer/video/7123456789012345678" in urls
