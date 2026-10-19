from src.downloader import is_valid_download_url, extract_video_id
from src.cookie_manager import generate_netscape_cookie_content, parse_and_validate_cookies


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


def test_parse_and_validate_cookies():
    # 1. Netscape without standard header
    raw_netscape = ".douyin.com\tTRUE\t/\tFALSE\t1800000000\tttwid\t1%7Cabc123\n.douyin.com\tTRUE\t/\tFALSE\t1800000000\tpassport_csrf_token\tcsrf456"
    parsed = parse_and_validate_cookies(raw_netscape)
    assert parsed is not None
    assert "# Netscape HTTP Cookie File" in parsed
    assert "ttwid" in parsed
    assert "passport_csrf_token" in parsed

    # 2. JSON array format
    raw_json = '[{"name": "ttwid", "value": "json_ttwid_999", "domain": ".douyin.com"}, {"name": "passport_csrf_token", "value": "json_csrf_888"}]'
    parsed_json = parse_and_validate_cookies(raw_json)
    assert parsed_json is not None
    assert "json_ttwid_999" in parsed_json
    assert "json_csrf_888" in parsed_json

    # 3. Semicolon-separated string
    raw_kv = "ttwid=kv_ttwid_777; passport_csrf_token=kv_csrf_666; other=val"
    parsed_kv = parse_and_validate_cookies(raw_kv)
    assert parsed_kv is not None
    assert "kv_ttwid_777" in parsed_kv
    assert "kv_csrf_666" in parsed_kv
