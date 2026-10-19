from src.downloader import is_valid_download_url, extract_video_id
from src.cookie_manager import generate_netscape_cookie_content


def test_url_validation():
    # Valid Douyin canonical
    assert is_valid_download_url("https://www.douyin.com/video/7391234567890123456")
    assert extract_video_id("https://www.douyin.com/video/7391234567890123456") == "7391234567890123456"

    # Douyin with trailing punctuation and query params
    assert is_valid_download_url("https://www.douyin.com/video/7391234567890123456...")
    assert extract_video_id("https://www.douyin.com/video/7391234567890123456...") == "7391234567890123456"

    assert is_valid_download_url("https://www.douyin.com/video/7391234567890123456,")
    assert extract_video_id("https://www.douyin.com/video/7391234567890123456,") == "7391234567890123456"

    assert is_valid_download_url("https://www.douyin.com/video/7391234567890123456?modal_id=123")
    assert extract_video_id("https://www.douyin.com/video/7391234567890123456?modal_id=123") == "7391234567890123456"

    # Valid TikTok canonical
    assert is_valid_download_url("https://www.tiktok.com/@dancer/video/7123456789012345678")
    assert extract_video_id("https://www.tiktok.com/@dancer/video/7123456789012345678") == "7123456789012345678"

    assert is_valid_download_url("https://www.tiktok.com/@dancer/video/7123456789012345678...")
    assert extract_video_id("https://www.tiktok.com/@dancer/video/7123456789012345678...") == "7123456789012345678"

    # Invalid non-video URLs
    assert not is_valid_download_url("https://www.douyin.com/user/12345")
    assert not is_valid_download_url("https://www.douyin.com/search/dance")
    assert not is_valid_download_url("invalid-url")


def test_netscape_cookie_generation():
    cookies = {
        "ttwid": "test_ttwid_token_12345",
        "passport_csrf_token": "test_csrf_token",
    }
    content = generate_netscape_cookie_content(cookies, domain=".douyin.com")
    assert "# Netscape HTTP Cookie File" in content
    assert "ttwid" in content
    assert "test_ttwid_token_12345" in content
    assert ".douyin.com" in content
