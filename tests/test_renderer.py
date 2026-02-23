"""Tests for devto_mirror.site_generation.renderer"""

import contextlib
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch


@contextlib.contextmanager
def _chdir(path: pathlib.Path):
    old = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class TestLoadPostsData(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            with _chdir(pathlib.Path(td)):
                result = renderer.load_posts_data()
        self.assertEqual(result, [])

    def test_invalid_json_returns_empty_list(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text("not valid json {{{", encoding="utf-8")
            with _chdir(root):
                result = renderer.load_posts_data()
        self.assertEqual(result, [])

    def test_valid_json_returns_posts(self):
        from devto_mirror.site_generation import renderer

        posts = [{"title": "A", "link": "https://dev.to/user/a-1"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root):
                result = renderer.load_posts_data()
        self.assertEqual(result, posts)

    def test_custom_path(self):
        from devto_mirror.site_generation import renderer

        posts = [{"title": "B"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "custom.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root):
                result = renderer.load_posts_data("custom.json")
        self.assertEqual(result, posts)


class TestSavePostsData(unittest.TestCase):
    def test_save_success(self):
        from devto_mirror.site_generation import renderer

        posts = [{"title": "A"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            with _chdir(root):
                result = renderer.save_posts_data(posts)
            self.assertTrue(result)
            saved = json.loads((root / "posts_data.json").read_text())
            self.assertEqual(saved, posts)

    def test_save_error_returns_false(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            with _chdir(root), patch("pathlib.Path.open", side_effect=IOError("Permission denied")):
                result = renderer.save_posts_data([{"title": "A"}])
        self.assertFalse(result)


class TestLoadAndMergePosts(unittest.TestCase):
    def test_no_new_file_returns_existing(self):
        from devto_mirror.site_generation import renderer

        posts = [
            {
                "title": "Existing",
                "link": "https://dev.to/user/existing-1",
                "slug": "existing-1",
                "date": "2024-01-01T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root):
                result = renderer.load_and_merge_posts()
        self.assertEqual(len(result), 1)

    def test_merges_new_with_existing(self):
        from devto_mirror.site_generation import renderer

        existing = [
            {
                "title": "Old",
                "link": "https://dev.to/user/old-1",
                "slug": "old-1",
                "date": "2024-01-01T00:00:00Z",
            }
        ]
        new_posts = [
            {
                "title": "New",
                "link": "https://dev.to/user/new-2",
                "slug": "new-2",
                "date": "2024-01-02T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(existing), encoding="utf-8")
            (root / "posts_data_new.json").write_text(json.dumps(new_posts), encoding="utf-8")
            with _chdir(root), patch("builtins.print"):
                result = renderer.load_and_merge_posts()
        self.assertEqual(len(result), 2)

    def test_new_file_invalid_json_falls_back_gracefully(self):
        from devto_mirror.site_generation import renderer

        existing = [{"title": "Old", "link": "https://dev.to/user/old-1", "slug": "old-1"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(existing), encoding="utf-8")
            (root / "posts_data_new.json").write_text("not valid json {{{", encoding="utf-8")
            with _chdir(root), patch("builtins.print"):
                result = renderer.load_and_merge_posts()
        # Should return existing posts without crashing
        self.assertEqual(len(result), 1)

    def test_new_file_empty_prints_message(self):
        from devto_mirror.site_generation import renderer

        existing = [{"title": "Old", "link": "https://dev.to/user/old-1", "slug": "old-1"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(existing), encoding="utf-8")
            (root / "posts_data_new.json").write_text(json.dumps([]), encoding="utf-8")
            with _chdir(root), patch("builtins.print") as mock_print:
                result = renderer.load_and_merge_posts()
        self.assertEqual(len(result), 1)
        all_printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("No new posts", all_printed)

    def test_merge_save_failure_prints_warning(self):
        from devto_mirror.site_generation import renderer

        existing = [{"title": "Old", "link": "https://dev.to/user/old-1", "slug": "old-1"}]
        new_posts = [{"title": "New", "link": "https://dev.to/user/new-2", "slug": "new-2"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(existing), encoding="utf-8")
            (root / "posts_data_new.json").write_text(json.dumps(new_posts), encoding="utf-8")
            with (
                _chdir(root),
                patch("builtins.print") as mock_print,
                patch("devto_mirror.site_generation.renderer.save_posts_data", return_value=False),
            ):
                renderer.load_and_merge_posts()
        all_printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("Warning", all_printed)


class TestLoadCommentManifest(unittest.TestCase):
    def test_no_comments_file_returns_empty(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            with _chdir(root):
                items = renderer.load_comment_manifest()
        self.assertEqual(items, [])

    def test_comment_id_from_fragment(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "comments.txt").write_text(
                "https://dev.to/user/post#comment-abc123|Nice comment\n",
                encoding="utf-8",
            )
            with _chdir(root):
                items = renderer.load_comment_manifest()
        self.assertEqual(len(items), 1)
        self.assertIn("abc123", items[0]["local"])

    def test_comment_id_from_path(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "comments.txt").write_text(
                "https://dev.to/comment/456|Some context\n",
                encoding="utf-8",
            )
            with _chdir(root):
                items = renderer.load_comment_manifest()
        self.assertEqual(len(items), 1)
        self.assertIn("456", items[0]["local"])

    def test_blank_lines_and_hash_comments_skipped(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "comments.txt").write_text(
                "# this is a comment\n\nhttps://dev.to/comment/789|Context\n",
                encoding="utf-8",
            )
            with _chdir(root):
                items = renderer.load_comment_manifest()
        self.assertEqual(len(items), 1)

    def test_label_truncated_at_80_chars(self):
        from devto_mirror.site_generation import renderer

        long_context = "x" * 100
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "comments.txt").write_text(
                f"https://dev.to/comment/abc|{long_context}\n",
                encoding="utf-8",
            )
            with _chdir(root):
                items = renderer.load_comment_manifest()
        self.assertEqual(len(items[0]["text"]), 80)
        self.assertTrue(items[0]["text"].endswith("..."))


class TestGetHomeUrl(unittest.TestCase):
    def test_site_domain_env_var(self):
        from devto_mirror.site_generation import renderer

        with patch.dict(os.environ, {"SITE_DOMAIN": "example.com", "GH_USERNAME": ""}):
            url = renderer.get_home_url()
        self.assertIn("example.com", url)

    def test_gh_username_env_var(self):
        from devto_mirror.site_generation import renderer

        with patch.dict(os.environ, {"GH_USERNAME": "testuser", "SITE_DOMAIN": ""}):
            url = renderer.get_home_url()
        self.assertIn("testuser", url)

    def test_neither_returns_empty_string(self):
        from devto_mirror.site_generation import renderer

        # Both empty → build_site_urls raises ValueError → returns ""
        with patch.dict(os.environ, {"SITE_DOMAIN": "", "GH_USERNAME": ""}):
            url = renderer.get_home_url()
        self.assertEqual(url, "")


class TestProcessComments(unittest.TestCase):
    def test_empty_manifest_returns_empty(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            with _chdir(root):
                result = renderer.process_comments("")
        self.assertEqual(result, [])

    def test_deduplicates_duplicate_comment_urls(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "comments.txt").write_text(
                "https://dev.to/comment/abc|First\nhttps://dev.to/comment/abc|Duplicate\n",
                encoding="utf-8",
            )
            with _chdir(root):
                result = renderer.process_comments("")
        self.assertEqual(len(result), 1)

    def test_home_prefix_applied(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "comments.txt").write_text(
                "https://dev.to/comment/abc|Context\n",
                encoding="utf-8",
            )
            with _chdir(root):
                result = renderer.process_comments("https://mysite.github.io/devto-mirror/")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://dev.to/comment/abc")


class TestGetTitleUser(unittest.TestCase):
    def test_devto_username_returned_directly(self):
        from devto_mirror.site_generation import renderer

        result = renderer.get_title_user([], "myuser")
        self.assertEqual(result, "myuser")

    def test_empty_posts_returns_empty_string(self):
        from devto_mirror.site_generation import renderer

        result = renderer.get_title_user([], "")
        self.assertEqual(result, "")

    def test_extracts_username_from_post_link(self):
        from devto_mirror.site_generation import renderer

        posts = [{"link": "https://dev.to/extracted_user/my-post-123"}]
        result = renderer.get_title_user(posts, "")
        self.assertEqual(result, "extracted_user")

    def test_post_with_no_link_returns_empty(self):
        from devto_mirror.site_generation import renderer

        posts = [{"title": "No link post"}]
        result = renderer.get_title_user(posts, "")
        self.assertEqual(result, "")

    def test_post_with_empty_link_returns_empty(self):
        from devto_mirror.site_generation import renderer

        posts = [{"link": ""}]
        result = renderer.get_title_user(posts, "")
        self.assertEqual(result, "")

    def test_exception_during_extraction_returns_empty(self):
        from devto_mirror.site_generation import renderer

        class BadPost(dict):
            """A post dict whose .get() raises, triggering the except branch."""

            def get(self, key, default=None):
                raise RuntimeError("access error for testing")

        with patch("sys.stderr"):
            result = renderer.get_title_user([BadPost()], "")
        self.assertEqual(result, "")

    def test_non_dict_post_with_link_attribute(self):
        from devto_mirror.site_generation import renderer

        class PostObj:
            link = "https://dev.to/attr_user/post-1"

        result = renderer.get_title_user([PostObj()], "")
        self.assertEqual(result, "attr_user")


if __name__ == "__main__":
    unittest.main()
