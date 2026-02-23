"""Tests for devto_mirror.core.article_fetcher"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from devto_mirror.core.article_fetcher import (
    _convert_cached_post_to_devto_article,
    _fetch_full_article_json,
    _fetch_full_articles,
    _try_load_cached_articles,
    fetch_all_articles_from_api,
)


class TestConvertCachedPost(unittest.TestCase):
    def test_non_dict_string_returns_none(self):
        result = _convert_cached_post_to_devto_article(item="not-a-dict", username="user")
        self.assertIsNone(result)

    def test_non_dict_list_returns_none(self):
        result = _convert_cached_post_to_devto_article(item=[1, 2, 3], username="user")
        self.assertIsNone(result)

    def test_non_dict_none_returns_none(self):
        result = _convert_cached_post_to_devto_article(item=None, username="user")
        self.assertIsNone(result)

    def test_api_data_not_dict_treated_as_empty(self):
        item = {"title": "Test", "link": "https://dev.to/user/test-1", "api_data": "not-a-dict"}
        result = _convert_cached_post_to_devto_article(item=item, username="user")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test")

    def test_api_data_none_treated_as_empty(self):
        item = {"title": "Test", "link": "https://dev.to/user/test-1", "api_data": None}
        result = _convert_cached_post_to_devto_article(item=item, username="user")
        self.assertIsNotNone(result)

    def test_valid_cached_post_converts(self):
        item = {
            "id": 42,
            "title": "Hello",
            "link": "https://dev.to/user/hello-42",
            "date": "2024-01-01T00:00:00Z",
            "api_data": {"id": 42, "published_at": "2024-01-01T00:00:00Z"},
        }
        result = _convert_cached_post_to_devto_article(item=item, username="user")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["title"], "Hello")
        self.assertEqual(result["user"]["username"], "user")

    def test_uses_url_field_if_link_missing(self):
        item = {"id": 1, "title": "T", "url": "https://dev.to/user/test-1"}
        result = _convert_cached_post_to_devto_article(item=item, username="user")
        self.assertEqual(result["url"], "https://dev.to/user/test-1")

    def test_empty_dict_returns_default_values(self):
        result = _convert_cached_post_to_devto_article(item={}, username="user")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Untitled")
        self.assertEqual(result["user"]["username"], "user")


class TestTryLoadCachedArticles(unittest.TestCase):
    def test_nonexistent_path_returns_empty(self):
        result = _try_load_cached_articles(posts_data_path="/nonexistent/path/posts.json", username="user")
        self.assertEqual(result, [])

    def test_empty_json_array_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([], f)
            fname = f.name
        try:
            result = _try_load_cached_articles(posts_data_path=fname, username="user")
            self.assertEqual(result, [])
        finally:
            os.unlink(fname)

    def test_mixed_valid_and_invalid_items(self):
        items = [
            {"id": 1, "title": "Valid", "link": "https://dev.to/user/valid-1"},
            "not-a-dict",
            None,
            {"id": 2, "title": "Also Valid", "link": "https://dev.to/user/valid-2"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(items, f)
            fname = f.name
        try:
            result = _try_load_cached_articles(posts_data_path=fname, username="user")
            self.assertEqual(len(result), 2)
        finally:
            os.unlink(fname)

    def test_invalid_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("not valid json }{")
            fname = f.name
        try:
            result = _try_load_cached_articles(posts_data_path=fname, username="user")
            self.assertEqual(result, [])
        finally:
            os.unlink(fname)

    def test_valid_cache_converts_all(self):
        items = [
            {"id": 1, "title": "Post A", "link": "https://dev.to/user/post-a-1"},
            {"id": 2, "title": "Post B", "link": "https://dev.to/user/post-b-2"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(items, f)
            fname = f.name
        try:
            result = _try_load_cached_articles(posts_data_path=fname, username="user")
            self.assertEqual(len(result), 2)
        finally:
            os.unlink(fname)


class TestFetchFullArticleJson(unittest.TestCase):
    def test_max_retries_zero_returns_none(self):
        session = MagicMock(spec=requests.Session)
        result = _fetch_full_article_json(session, article_id=123, max_retries=0)
        self.assertIsNone(result)
        session.get.assert_not_called()

    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_read_timeout_retries_then_fails(self, mock_sleep):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.ReadTimeout("Timeout")
        result = _fetch_full_article_json(session, article_id=123, max_retries=2)
        self.assertIsNone(result)
        self.assertEqual(session.get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_connection_error_retries_then_fails(self, mock_sleep):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.ConnectionError("Connection reset")
        result = _fetch_full_article_json(session, article_id=123, max_retries=2)
        self.assertIsNone(result)
        self.assertEqual(session.get.call_count, 2)

    def test_request_exception_fails_immediately_without_retry(self):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.HTTPError("404 Not Found")
        result = _fetch_full_article_json(session, article_id=123, max_retries=3)
        self.assertIsNone(result)
        self.assertEqual(session.get.call_count, 1)

    def test_success_returns_json(self):
        session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "title": "Test Article"}
        session.get.return_value = mock_response
        result = _fetch_full_article_json(session, article_id=123)
        self.assertEqual(result, {"id": 123, "title": "Test Article"})

    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_timeout_then_success(self, mock_sleep):
        session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "title": "Test"}
        session.get.side_effect = [
            requests.exceptions.ReadTimeout("Timeout"),
            mock_response,
        ]
        result = _fetch_full_article_json(session, article_id=123, max_retries=3)
        self.assertEqual(result, {"id": 123, "title": "Test"})
        mock_sleep.assert_called_once()

    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1}
        session.get.side_effect = [
            requests.exceptions.ReadTimeout("T1"),
            requests.exceptions.ReadTimeout("T2"),
            mock_response,
        ]
        _fetch_full_article_json(session, article_id=1, max_retries=3, initial_retry_delay=2)
        # First sleep=2, second sleep=4
        self.assertEqual(mock_sleep.call_args_list[0][0][0], 2)
        self.assertEqual(mock_sleep.call_args_list[1][0][0], 4)


class TestFetchFullArticles(unittest.TestCase):
    @patch("devto_mirror.core.article_fetcher.create_devto_session")
    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_session_created_and_closed(self, mock_sleep, mock_create_session):
        mock_session = MagicMock(spec=requests.Session)
        mock_create_session.return_value = mock_session
        with patch("devto_mirror.core.article_fetcher._fetch_full_article_json", return_value={"id": 1}):
            full, failed = _fetch_full_articles(article_summaries=[{"id": 1}])
        mock_session.close.assert_called_once()
        self.assertEqual(len(full), 1)

    @patch("devto_mirror.core.article_fetcher.create_devto_session")
    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_failed_articles_tracked(self, mock_sleep, mock_create_session):
        mock_session = MagicMock(spec=requests.Session)
        mock_create_session.return_value = mock_session
        with patch("devto_mirror.core.article_fetcher._fetch_full_article_json") as mock_fetch:
            mock_fetch.side_effect = [{"id": 1, "title": "Success"}, None]
            full, failed = _fetch_full_articles(article_summaries=[{"id": 1}, {"id": 2}])
        self.assertEqual(len(full), 1)
        self.assertEqual(full[0]["title"], "Success")
        self.assertEqual(len(failed), 1)

    @patch("devto_mirror.core.article_fetcher.create_devto_session")
    def test_single_article_no_sleep_between(self, mock_create_session):
        """With only one article, no sleep should be called between articles."""
        mock_session = MagicMock(spec=requests.Session)
        mock_create_session.return_value = mock_session
        with (
            patch("devto_mirror.core.article_fetcher._fetch_full_article_json", return_value={"id": 1}),
            patch("devto_mirror.core.article_fetcher.time.sleep") as mock_sleep,
        ):
            full, failed = _fetch_full_articles(article_summaries=[{"id": 1}])
        mock_sleep.assert_not_called()
        self.assertEqual(len(full), 1)

    @patch("devto_mirror.core.article_fetcher.create_devto_session")
    @patch("devto_mirror.core.article_fetcher.time.sleep")
    def test_sleep_between_multiple_articles(self, mock_sleep, mock_create_session):
        mock_session = MagicMock(spec=requests.Session)
        mock_create_session.return_value = mock_session
        with patch(
            "devto_mirror.core.article_fetcher._fetch_full_article_json",
            side_effect=[{"id": 1}, {"id": 2}],
        ):
            _fetch_full_articles(article_summaries=[{"id": 1}, {"id": 2}])
        # Sleep called once between articles (not after the last one)
        self.assertEqual(mock_sleep.call_count, 1)
        mock_sleep.assert_called_with(0.8)


class TestFetchAllArticlesFromApi(unittest.TestCase):
    @patch.dict("os.environ", {"DEVTO_MIRROR_FORCE_EMPTY_FEED": "true"})
    def test_force_empty_feed_with_last_run(self):
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso="2025-01-01T00:00:00+00:00",
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertTrue(result.success)
        self.assertTrue(result.no_new_posts)
        self.assertEqual(result.source, "forced-empty")
        self.assertEqual(result.articles, [])

    @patch.dict("os.environ", {"DEVTO_MIRROR_FORCE_EMPTY_FEED": "1"})
    def test_force_empty_feed_without_last_run(self):
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertFalse(result.no_new_posts)
        self.assertEqual(result.source, "forced-empty")

    @patch.dict("os.environ", {"DEVTO_MIRROR_FORCE_EMPTY_FEED": "yes"})
    def test_force_empty_feed_yes_value(self):
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertEqual(result.source, "forced-empty")

    @patch.dict("os.environ", {"VALIDATION_NO_POSTS": "true"})
    def test_validation_no_posts_env_var(self):
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=True,
            )
        self.assertTrue(result.success)
        self.assertEqual(result.articles, [])
        self.assertEqual(result.source, "validation")
        self.assertFalse(result.no_new_posts)

    def test_validation_mode_returns_mock_article(self):
        old_env = os.environ.copy()
        try:
            os.environ.pop("VALIDATION_NO_POSTS", None)
            with tempfile.TemporaryDirectory() as td:
                result = fetch_all_articles_from_api(
                    username="testuser",
                    last_run_iso=None,
                    posts_data_path=Path(td) / "posts_data.json",
                    validation_mode=True,
                )
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        self.assertTrue(result.success)
        self.assertEqual(len(result.articles), 1)
        self.assertEqual(result.source, "mock")
        self.assertIn("testuser", result.articles[0]["url"])

    @patch("devto_mirror.core.article_fetcher._fetch_article_pages")
    def test_no_summaries_with_last_run_iso_returns_no_new(self, mock_fetch_pages):
        mock_fetch_pages.return_value = []
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso="2025-01-01T00:00:00+00:00",
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertTrue(result.no_new_posts)
        self.assertEqual(result.source, "api")

    @patch("devto_mirror.core.article_fetcher._fetch_article_pages")
    def test_no_summaries_without_last_run_iso(self, mock_fetch_pages):
        mock_fetch_pages.return_value = []
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertFalse(result.no_new_posts)
        self.assertEqual(result.source, "api")

    @patch("devto_mirror.core.article_fetcher._fetch_article_pages")
    @patch("devto_mirror.core.article_fetcher._fetch_full_articles")
    def test_fallback_to_cache_when_full_articles_empty(self, mock_full, mock_pages):
        mock_pages.return_value = [{"id": 1}]
        mock_full.return_value = ([], [{"id": 1}])
        with tempfile.TemporaryDirectory() as td:
            posts_path = Path(td) / "posts_data.json"
            posts_path.write_text(
                json.dumps([{"id": 1, "title": "Cached", "link": "https://dev.to/user/cached-1"}]),
                encoding="utf-8",
            )
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=posts_path,
                validation_mode=False,
            )
        self.assertFalse(result.success)
        self.assertEqual(result.source, "cache")
        self.assertTrue(result.articles)

    @patch("devto_mirror.core.article_fetcher._fetch_article_pages")
    @patch("devto_mirror.core.article_fetcher._fetch_full_articles")
    def test_fallback_to_cache_on_exception(self, mock_full, mock_pages):
        mock_pages.return_value = [{"id": 1}]
        mock_full.side_effect = Exception("Network error")
        with tempfile.TemporaryDirectory() as td:
            posts_path = Path(td) / "posts_data.json"
            posts_path.write_text(
                json.dumps([{"id": 1, "title": "Cached", "link": "https://dev.to/user/cached-1"}]),
                encoding="utf-8",
            )
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=posts_path,
                validation_mode=False,
            )
        self.assertFalse(result.success)
        self.assertEqual(result.source, "cache")

    @patch("devto_mirror.core.article_fetcher._fetch_article_pages")
    @patch("devto_mirror.core.article_fetcher._fetch_full_articles")
    def test_success_returns_full_articles(self, mock_full, mock_pages):
        mock_pages.return_value = [{"id": 1}]
        mock_full.return_value = ([{"id": 1, "title": "Full Article"}], [])
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertTrue(result.success)
        self.assertEqual(result.source, "api")
        self.assertEqual(result.articles[0]["title"], "Full Article")

    @patch("devto_mirror.core.article_fetcher._fetch_article_pages")
    @patch("devto_mirror.core.article_fetcher._fetch_full_articles")
    def test_cache_fallback_with_empty_cache_file(self, mock_full, mock_pages):
        """When cache file doesn't exist, fallback returns empty articles list."""
        mock_pages.return_value = [{"id": 1}]
        mock_full.return_value = ([], [{"id": 1}])
        with tempfile.TemporaryDirectory() as td:
            result = fetch_all_articles_from_api(
                username="testuser",
                last_run_iso=None,
                posts_data_path=Path(td) / "posts_data.json",
                validation_mode=False,
            )
        self.assertFalse(result.success)
        self.assertEqual(result.source, "cache")
        self.assertEqual(result.articles, [])


if __name__ == "__main__":
    unittest.main()
