"""Tests for devto_mirror.tools.clean_posts"""

import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import devto_mirror.tools.clean_posts as clean_posts_module
from devto_mirror.tools.clean_posts import dedupe_posts, key_for


class TestKeyFor(unittest.TestCase):
    def test_key_for_with_link_strips_trailing_slash(self):
        post = {"link": "https://example.com/post/", "slug": "post-slug"}
        self.assertEqual(key_for(post), "https://example.com/post")

    def test_key_for_with_link_no_slash(self):
        post = {"link": "https://example.com/post", "slug": "post-slug"}
        self.assertEqual(key_for(post), "https://example.com/post")

    def test_key_for_falls_back_to_slug(self):
        post = {"link": "", "slug": "post-slug"}
        self.assertEqual(key_for(post), "post-slug")

    def test_key_for_none_link_falls_back_to_slug(self):
        post = {"link": None, "slug": "post-slug"}
        self.assertEqual(key_for(post), "post-slug")

    def test_key_for_empty_link_and_slug_returns_empty(self):
        # When both are empty, key_for returns ""; dedupe_posts uses title as fallback
        post = {"slug": "", "link": ""}
        self.assertEqual(key_for(post), "")


class TestDedupePosts(unittest.TestCase):
    def test_keeps_newest_by_date(self):
        a = {"link": "https://example.com/post", "date": "2024-01-01T00:00:00Z"}
        b = {"link": "https://example.com/post", "date": "2024-01-02T00:00:00Z"}
        result = dedupe_posts([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2024-01-02T00:00:00Z")

    def test_handles_none_date_in_existing(self):
        # a (existing) has no date, b has date → keeps b
        a = {"link": "https://example.com/post"}
        b = {"link": "https://example.com/post", "date": "2024-01-02T00:00:00Z"}
        result = dedupe_posts([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2024-01-02T00:00:00Z")

    def test_handles_none_date_in_incoming(self):
        # a has date, b has no date → keeps a (existing)
        a = {"link": "https://example.com/post", "date": "2024-01-01T00:00:00Z"}
        b = {"link": "https://example.com/post"}
        result = dedupe_posts([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2024-01-01T00:00:00Z")

    def test_handles_both_none_dates(self):
        # Both dates None → keep existing (first one added)
        a = {"link": "https://example.com/post", "title": "First"}
        b = {"link": "https://example.com/post", "title": "Second"}
        result = dedupe_posts([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "First")

    def test_returns_single_post_unchanged(self):
        a = {"link": "https://example.com/post", "date": "2024-01-01T00:00:00Z"}
        result = dedupe_posts([a])
        self.assertEqual(len(result), 1)

    def test_fallback_to_title_as_key(self):
        # No link, no slug → uses title as key in dedupe_posts
        a = {"title": "My Post", "link": "", "slug": ""}
        b = {"title": "Other Post", "link": "", "slug": ""}
        result = dedupe_posts([a, b])
        self.assertEqual(len(result), 2)

    def test_deduplicates_with_title_fallback(self):
        # Two posts with same title, no link/slug → deduplicated
        a = {"title": "Same Title", "link": "", "slug": "", "date": "2024-01-01T00:00:00Z"}
        b = {"title": "Same Title", "link": "", "slug": "", "date": "2024-01-02T00:00:00Z"}
        result = dedupe_posts([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2024-01-02T00:00:00Z")

    def test_multiple_unique_posts(self):
        posts = [
            {"link": "https://example.com/a", "date": "2024-01-01T00:00:00Z"},
            {"link": "https://example.com/b", "date": "2024-01-02T00:00:00Z"},
            {"link": "https://example.com/c", "date": "2024-01-03T00:00:00Z"},
        ]
        result = dedupe_posts(posts)
        self.assertEqual(len(result), 3)


class TestCleanPostsMain(unittest.TestCase):
    def _make_temp_paths(self):
        td = tempfile.mkdtemp()
        data_file = pathlib.Path(td) / "posts_data.json"
        backup_file = pathlib.Path(td) / "posts_data.json.bak"
        return data_file, backup_file

    def test_no_posts_file_returns_early(self):
        data_file, backup_file = self._make_temp_paths()
        with (
            patch.object(clean_posts_module, "DATA_FILE", data_file),
            patch.object(clean_posts_module, "BACKUP_FILE", backup_file),
            patch("builtins.print") as mock_print,
        ):
            clean_posts_module.main()
        all_printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("No", all_printed)
        self.assertFalse(backup_file.exists())

    def test_creates_backup_on_first_run(self):
        data_file, backup_file = self._make_temp_paths()
        posts = [{"link": "https://example.com/post", "date": "2024-01-01T00:00:00Z", "title": "A"}]
        data_file.write_text(json.dumps(posts), encoding="utf-8")
        with (
            patch.object(clean_posts_module, "DATA_FILE", data_file),
            patch.object(clean_posts_module, "BACKUP_FILE", backup_file),
            patch("builtins.print"),
        ):
            clean_posts_module.main()
        self.assertTrue(backup_file.exists())

    def test_no_backup_if_already_exists(self):
        data_file, backup_file = self._make_temp_paths()
        posts = [{"link": "https://example.com/post", "date": "2024-01-01T00:00:00Z", "title": "A"}]
        data_file.write_text(json.dumps(posts), encoding="utf-8")
        backup_file.write_text("original backup content", encoding="utf-8")
        with (
            patch.object(clean_posts_module, "DATA_FILE", data_file),
            patch.object(clean_posts_module, "BACKUP_FILE", backup_file),
            patch("builtins.print"),
        ):
            clean_posts_module.main()
        # Backup should be unchanged
        self.assertEqual(backup_file.read_text(), "original backup content")

    def test_saves_deduped_sorted_posts(self):
        data_file, backup_file = self._make_temp_paths()
        posts = [
            {"link": "https://example.com/post", "date": "2024-01-01T00:00:00Z", "title": "Old"},
            {"link": "https://example.com/post", "date": "2024-01-02T00:00:00Z", "title": "New"},
        ]
        data_file.write_text(json.dumps(posts), encoding="utf-8")
        with (
            patch.object(clean_posts_module, "DATA_FILE", data_file),
            patch.object(clean_posts_module, "BACKUP_FILE", backup_file),
            patch("builtins.print"),
        ):
            clean_posts_module.main()
        result = json.loads(data_file.read_text())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "New")

    def test_json_load_error_propagates(self):
        data_file, backup_file = self._make_temp_paths()
        data_file.write_text("not valid json", encoding="utf-8")
        with (
            patch.object(clean_posts_module, "DATA_FILE", data_file),
            patch.object(clean_posts_module, "BACKUP_FILE", backup_file),
        ):
            with self.assertRaises(Exception):
                clean_posts_module.main()

    def test_multiple_posts_sorted_newest_first(self):
        data_file, backup_file = self._make_temp_paths()
        posts = [
            {"link": "https://example.com/old", "date": "2024-01-01T00:00:00Z", "title": "Old"},
            {"link": "https://example.com/new", "date": "2024-01-03T00:00:00Z", "title": "New"},
            {"link": "https://example.com/mid", "date": "2024-01-02T00:00:00Z", "title": "Mid"},
        ]
        data_file.write_text(json.dumps(posts), encoding="utf-8")
        with (
            patch.object(clean_posts_module, "DATA_FILE", data_file),
            patch.object(clean_posts_module, "BACKUP_FILE", backup_file),
            patch("builtins.print"),
        ):
            clean_posts_module.main()
        result = json.loads(data_file.read_text())
        self.assertEqual(len(result), 3)
        # Should be sorted newest first
        self.assertEqual(result[0]["title"], "New")


if __name__ == "__main__":
    unittest.main()
