"""
Tests for the Dev.to API client utilities.
"""

import unittest
from datetime import timezone
from unittest.mock import MagicMock, patch

import requests

from devto_mirror.core.api_client import (
    _parse_api_timestamp,
    create_devto_session,
    fetch_page_with_retry,
    filter_new_articles,
)


class TestCreateDevtoSession(unittest.TestCase):
    """Test cases for create_devto_session function."""

    def setUp(self):
        """Set up test fixtures."""
        self.session = None

    def tearDown(self):
        """Clean up resources."""
        if self.session is not None:
            self.session.close()

    @patch.dict("os.environ", {}, clear=True)
    def test_creates_session_with_default_headers(self):
        """Test session creation with default (non-CI) headers."""
        self.session = create_devto_session()

        self.assertIsInstance(self.session, requests.Session)
        self.assertEqual(self.session.headers["User-Agent"], "DevTo-Mirror-Bot/1.0")
        self.assertEqual(self.session.headers["Accept"], "application/vnd.forem.api-v1+json")
        self.assertNotIn("api-key", self.session.headers)

    @patch.dict("os.environ", {"CI": "true"}, clear=True)
    def test_creates_session_with_ci_user_agent(self):
        """Test session creation in CI environment."""
        self.session = create_devto_session()

        self.assertEqual(self.session.headers["User-Agent"], "DevTo-Mirror-Bot/1.0 (GitHub-Actions)")

    @patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=True)
    def test_creates_session_with_github_actions_detection(self):
        """Test session creation with GITHUB_ACTIONS env var."""
        self.session = create_devto_session()

        self.assertEqual(self.session.headers["User-Agent"], "DevTo-Mirror-Bot/1.0 (GitHub-Actions)")

    @patch.dict("os.environ", {"DEVTO_KEY": "not-a-real-thing"}, clear=True)
    def test_includes_api_key_when_provided(self):
        """Test that API key is included in headers when env var is set."""
        self.session = create_devto_session()

        self.assertEqual(self.session.headers["api-key"], "not-a-real-thing")

    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key_when_not_provided(self):
        """Test that api-key header is absent when env var is not set."""
        self.session = create_devto_session()

        self.assertNotIn("api-key", self.session.headers)


class TestFetchPageWithRetry(unittest.TestCase):
    """Test cases for fetch_page_with_retry function."""

    def setUp(self):
        """Set up test fixtures."""
        self.session = MagicMock(spec=requests.Session)
        self.url = "https://dev.to/api/articles"
        self.params = {"username": "testuser", "page": 1}

    def test_successful_fetch_returns_list_of_dicts(self):
        """Test successful API response returns parsed JSON as List[dict]."""
        expected_data = [{"id": 1, "title": "Test Article"}]
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data
        self.session.get.return_value = mock_response

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], dict)
        self.assertEqual(result, expected_data)
        self.session.get.assert_called_once_with(self.url, params=self.params, timeout=30)

    def test_returns_none_on_request_exception(self):
        """Test that RequestException returns None without retry."""
        self.session.get.side_effect = requests.exceptions.RequestException("Connection failed")

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1)

        self.assertIsNone(result)
        self.assertEqual(self.session.get.call_count, 1)

    @patch("devto_mirror.core.api_client.time.sleep")
    def test_retries_on_timeout(self, mock_sleep):
        """Test that timeout triggers retry with exponential backoff."""
        expected_data = [{"id": 1}]
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data

        self.session.get.side_effect = [
            requests.exceptions.ReadTimeout("Timeout"),
            mock_response,
        ]

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1, max_retries=3)

        self.assertEqual(result, expected_data)
        self.assertEqual(self.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("devto_mirror.core.api_client.time.sleep")
    def test_retries_on_connection_error(self, mock_sleep):
        """Test that ConnectionError triggers retry."""
        expected_data = [{"id": 1}]
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data

        self.session.get.side_effect = [
            requests.exceptions.ConnectionError("Connection reset"),
            mock_response,
        ]

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1, max_retries=3)

        self.assertEqual(result, expected_data)
        self.assertEqual(self.session.get.call_count, 2)

    @patch("devto_mirror.core.api_client.time.sleep")
    def test_returns_none_after_max_retries_exhausted(self, mock_sleep):
        """Test that None is returned after all retries fail."""
        self.session.get.side_effect = requests.exceptions.ReadTimeout("Persistent timeout")

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1, max_retries=3)

        self.assertIsNone(result)
        self.assertEqual(self.session.get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("devto_mirror.core.api_client.time.sleep")
    def test_exponential_backoff_delay(self, mock_sleep):
        """Test that retry delay doubles with each attempt."""
        expected_data = [{"id": 1}]
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data

        self.session.get.side_effect = [
            requests.exceptions.ReadTimeout("Timeout 1"),
            requests.exceptions.ReadTimeout("Timeout 2"),
            mock_response,
        ]

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1, max_retries=3)

        self.assertEqual(result, expected_data)
        self.assertEqual(mock_sleep.call_args_list[0][0][0], 1)
        self.assertEqual(mock_sleep.call_args_list[1][0][0], 2)

    def test_custom_timeout_parameter(self):
        """Test that custom timeout is passed to session.get."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        self.session.get.return_value = mock_response

        fetch_page_with_retry(self.session, self.url, self.params, page=1, timeout=60)

        self.session.get.assert_called_once_with(self.url, params=self.params, timeout=60)

    def test_http_error_does_not_retry(self):
        """Test that HTTP errors (4xx, 5xx) fail immediately without retry."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        self.session.get.return_value = mock_response

        result = fetch_page_with_retry(self.session, self.url, self.params, page=1, max_retries=3)

        self.assertIsNone(result)
        self.assertEqual(self.session.get.call_count, 1)


class TestFilterNewArticles(unittest.TestCase):
    """Test cases for filter_new_articles function."""

    def test_returns_all_articles_when_no_last_run(self):
        """Test that all articles are returned when last_run_iso is None."""
        articles = [
            {"id": 1, "published_at": "2024-01-01T00:00:00Z"},
            {"id": 2, "published_at": "2024-01-02T00:00:00Z"},
        ]

        result = filter_new_articles(articles, None)

        self.assertEqual(result, articles)

    def test_filters_articles_after_last_run(self):
        """Test that only articles with activity after last_run are returned."""
        articles = [
            {"id": 1, "published_at": "2024-01-01T00:00:00Z"},
            {"id": 2, "published_at": "2024-01-03T00:00:00Z"},
            {"id": 3, "published_at": "2024-01-05T00:00:00Z"},
        ]
        last_run = "2024-01-02T00:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 2)
        self.assertEqual(result[1]["id"], 3)

    def test_excludes_articles_equal_to_last_run(self):
        """Test that articles at exactly last_run time are excluded."""
        articles = [
            {"id": 1, "published_at": "2024-01-02T00:00:00Z"},
        ]
        last_run = "2024-01-02T00:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual(result, [])

    def test_handles_empty_article_list(self):
        """Test handling of empty article list."""
        result = filter_new_articles([], "2024-01-01T00:00:00+00:00")

        self.assertEqual(result, [])

    def test_handles_timezone_aware_timestamps(self):
        """Test proper handling of timezone-aware timestamps."""
        articles = [
            {"id": 1, "published_at": "2024-01-02T12:00:00Z"},
        ]
        last_run = "2024-01-02T06:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)

    def test_handles_z_suffix_conversion(self):
        """Test that Z suffix is properly converted to +00:00."""
        articles = [
            {"id": 1, "published_at": "2024-06-15T10:30:00Z"},
        ]
        last_run = "2024-06-15T08:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual(len(result), 1)

    def test_raises_value_error_for_invalid_iso_format(self):
        """Test that invalid ISO format raises ValueError."""
        articles = [{"id": 1, "published_at": "2024-01-01T00:00:00Z"}]

        with self.assertRaises(ValueError) as context:
            filter_new_articles(articles, "not-a-valid-timestamp")

        self.assertIn("must be valid ISO 8601 format", str(context.exception))

    def test_raises_value_error_for_malformed_date(self):
        """Test that malformed date string raises ValueError."""
        articles = [{"id": 1, "published_at": "2024-01-01T00:00:00Z"}]

        with self.assertRaises(ValueError):
            filter_new_articles(articles, "2024-13-45T99:99:99")

    def test_empty_string_returns_all_articles(self):
        """Test that empty string is treated as falsy (returns all articles)."""
        articles = [{"id": 1, "published_at": "2024-01-01T00:00:00Z"}]

        result = filter_new_articles(articles, "")

        self.assertEqual(result, articles)

    def test_skips_articles_with_no_activity_timestamp(self):
        """Test that articles missing edited/updated/published timestamps are skipped."""
        articles = [
            {"id": 1, "published_at": "2024-01-03T00:00:00Z"},
            {"id": 2},
            {"id": 3, "published_at": "2024-01-05T00:00:00Z"},
        ]
        last_run = "2024-01-02T00:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[1]["id"], 3)

    def test_skips_articles_with_malformed_published_at(self):
        """Test that articles with no parseable activity timestamp are skipped."""
        articles = [
            {"id": 1, "published_at": "2024-01-03T00:00:00Z"},
            {"id": 2, "published_at": "not-a-date"},
            {"id": 3, "published_at": "2024-01-05T00:00:00Z"},
        ]
        last_run = "2024-01-02T00:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[1]["id"], 3)

    def test_includes_articles_edited_after_last_run_even_if_published_before(self):
        articles = [
            {
                "id": 1,
                "published_at": "2024-01-01T00:00:00Z",
                "edited_at": "2024-01-03T00:00:00Z",
            },
            {
                "id": 2,
                "published_at": "2024-01-01T00:00:00Z",
                "edited_at": "2024-01-01T12:00:00Z",
            },
        ]
        last_run = "2024-01-02T00:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual([a["id"] for a in result], [1])

    def test_includes_articles_with_only_edited_at(self):
        articles = [
            {"id": 1, "edited_at": "2024-01-03T00:00:00Z"},
            {"id": 2},
        ]
        last_run = "2024-01-02T00:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual([a["id"] for a in result], [1])

    def test_prefers_most_recent_activity_timestamp(self):
        articles = [
            {
                "id": 1,
                "published_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-03T00:00:00Z",
                "edited_at": "2024-01-04T00:00:00Z",
            }
        ]
        last_run = "2024-01-03T12:00:00+00:00"

        result = filter_new_articles(articles, last_run)

        self.assertEqual([a["id"] for a in result], [1])


class TestParseApiTimestamp(unittest.TestCase):
    """Test cases for the _parse_api_timestamp helper."""

    def test_none_returns_none(self):
        self.assertIsNone(_parse_api_timestamp(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_api_timestamp(""))

    def test_zero_returns_none(self):
        self.assertIsNone(_parse_api_timestamp(0))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_parse_api_timestamp("not-a-date"))

    def test_valid_z_suffix_utc_string(self):
        result = _parse_api_timestamp("2024-01-01T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)
        self.assertEqual(result.year, 2024)

    def test_naive_datetime_string_gets_utc(self):
        """Naive ISO string (no timezone) should be given UTC tzinfo."""
        result = _parse_api_timestamp("2024-06-15T12:30:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.hour, 12)

    def test_timezone_aware_string(self):
        result = _parse_api_timestamp("2024-01-01T00:00:00+00:00")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)


class TestFilterNewArticlesExtra(unittest.TestCase):
    """Extra coverage for filter_new_articles – naive last_run_iso normalization."""

    def test_naive_last_run_iso_is_utc_normalized(self):
        """last_run_iso without timezone → treated as UTC (line 149 in api_client)."""
        articles = [
            {"id": 1, "published_at": "2024-01-03T00:00:00Z"},
            {"id": 2, "published_at": "2024-01-01T00:00:00Z"},
        ]
        # "2024-01-02T00:00:00" has no timezone; should be treated as UTC
        result = filter_new_articles(articles, "2024-01-02T00:00:00")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)

    def test_all_articles_none_timestamp_skipped(self):
        """Articles with only None/missing timestamps are all skipped."""
        articles = [{"id": 1}, {"id": 2}]
        result = filter_new_articles(articles, "2024-01-02T00:00:00+00:00")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
