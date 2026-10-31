import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from src.youtube_uploader import upload_youtube_shorts, get_youtube_client


class TestYouTubeUploader(unittest.TestCase):
    def test_dry_run_returns_mock_id(self):
        video_id = upload_youtube_shorts(
            client_id="dummy_client_id",
            client_secret="dummy_client_secret",
            refresh_token="dummy_refresh_token",
            video_filepath="dummy.mp4",
            title="Test Dance Cover #shorts",
            description="Test description",
            tags=["dance", "shorts"],
            dry_run=True,
        )
        self.assertEqual(video_id, "mock_yt_id_12345")

    def test_missing_credentials_in_production_returns_none(self):
        video_id = upload_youtube_shorts(
            client_id=None,
            client_secret=None,
            refresh_token=None,
            video_filepath="dummy.mp4",
            title="Test Dance Cover #shorts",
            description="Test description",
            tags=["dance", "shorts"],
            dry_run=False,
        )
        self.assertIsNone(video_id)

    def test_missing_credentials_in_dry_run_returns_mock_id(self):
        video_id = upload_youtube_shorts(
            client_id=None,
            client_secret=None,
            refresh_token=None,
            video_filepath="dummy.mp4",
            title="Test Dance Cover #shorts",
            description="Test description",
            tags=["dance", "shorts"],
            dry_run=True,
        )
        self.assertEqual(video_id, "mock_yt_id_12345")

    @patch("src.youtube_uploader.MediaFileUpload")
    @patch("src.youtube_uploader.get_youtube_client")
    def test_upload_with_custom_privacy_private(self, mock_get_client, mock_media):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (MagicMock(progress=lambda: 1.0), {"id": "real_yt_test_id"})
        mock_service.videos().insert.return_value = mock_request
        mock_get_client.return_value = mock_service

        video_id = upload_youtube_shorts(
            client_id="cid",
            client_secret="csecret",
            refresh_token="rtoken",
            video_filepath="dummy.mp4",
            title="Test Private Upload",
            description="Desc",
            tags=["dance"],
            privacy_status="private",
            dry_run=False,
        )

        self.assertEqual(video_id, "real_yt_test_id")
        insert_kwargs = mock_service.videos().insert.call_args[1]
        body = insert_kwargs["body"]
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertNotIn("publishAt", body["status"])

    @patch("src.youtube_uploader.MediaFileUpload")
    @patch("src.youtube_uploader.get_youtube_client")
    def test_upload_with_custom_privacy_unlisted(self, mock_get_client, mock_media):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (MagicMock(progress=lambda: 1.0), {"id": "unlisted_id"})
        mock_service.videos().insert.return_value = mock_request
        mock_get_client.return_value = mock_service

        video_id = upload_youtube_shorts(
            client_id="cid",
            client_secret="csecret",
            refresh_token="rtoken",
            video_filepath="dummy.mp4",
            title="Test Unlisted Upload",
            description="Desc",
            tags=["dance"],
            privacy_status="unlisted",
            dry_run=False,
        )

        self.assertEqual(video_id, "unlisted_id")
        insert_kwargs = mock_service.videos().insert.call_args[1]
        body = insert_kwargs["body"]
        self.assertEqual(body["status"]["privacyStatus"], "unlisted")
        self.assertNotIn("publishAt", body["status"])

    @patch("src.youtube_uploader.MediaFileUpload")
    @patch("src.youtube_uploader.get_youtube_client")
    def test_upload_scheduled_when_no_privacy_override(self, mock_get_client, mock_media):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (MagicMock(progress=lambda: 1.0), {"id": "sched_id"})
        mock_service.videos().insert.return_value = mock_request
        mock_get_client.return_value = mock_service

        sched_time = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
        video_id = upload_youtube_shorts(
            client_id="cid",
            client_secret="csecret",
            refresh_token="rtoken",
            video_filepath="dummy.mp4",
            title="Test Sched Upload",
            description="Desc",
            tags=["dance"],
            publish_at=sched_time,
            privacy_status=None,
            dry_run=False,
        )

        self.assertEqual(video_id, "sched_id")
        insert_kwargs = mock_service.videos().insert.call_args[1]
        body = insert_kwargs["body"]
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(body["status"]["publishAt"], "2026-11-01T12:00:00.000Z")

    @patch("src.youtube_uploader.MediaFileUpload")
    @patch("src.youtube_uploader.get_youtube_client")
    def test_upload_handles_failure(self, mock_get_client, mock_media):
        mock_service = MagicMock()
        mock_service.videos().insert.side_effect = Exception("API Quota Exceeded")
        mock_get_client.return_value = mock_service

        video_id = upload_youtube_shorts(
            client_id="cid",
            client_secret="csecret",
            refresh_token="rtoken",
            video_filepath="dummy.mp4",
            title="Test Error",
            description="Desc",
            tags=["dance"],
            dry_run=False,
        )

        self.assertIsNone(video_id)


if __name__ == "__main__":
    unittest.main()
