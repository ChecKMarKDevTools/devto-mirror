"""Tests for devto_mirror.tools.fix_slugs"""

import contextlib
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from devto_mirror.tools.fix_slugs import _safe_path, extract_slug_from_url


@contextlib.contextmanager
def _chdir(path: pathlib.Path):
    old = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class TestExtractSlugFromUrl(unittest.TestCase):
    def test_returns_none_for_none_input(self):
        self.assertIsNone(extract_slug_from_url(None))

    def test_returns_none_for_empty_string(self):
        self.assertIsNone(extract_slug_from_url(""))

    def test_returns_none_for_no_protocol(self):
        # No '//' in URL – early return on line 16
        self.assertIsNone(extract_slug_from_url("dev.to/user/slug"))

    def test_returns_none_for_too_few_path_parts(self):
        # Has '//' but only 2 parts after domain (needs 3: domain/user/slug)
        self.assertIsNone(extract_slug_from_url("https://dev.to/user"))

    def test_returns_none_for_domain_only(self):
        self.assertIsNone(extract_slug_from_url("https://dev.to"))

    def test_returns_slug_for_valid_url(self):
        result = extract_slug_from_url("https://dev.to/username/my-post-123")
        self.assertEqual(result, "my-post-123")

    def test_handles_url_with_extra_trailing_parts(self):
        result = extract_slug_from_url("https://dev.to/username/my-post-123/extra")
        self.assertEqual(result, "my-post-123")

    def test_returns_none_for_empty_slug_segment(self):
        # Three parts but empty slug
        self.assertIsNone(extract_slug_from_url("https://dev.to//"))


class TestSafePath(unittest.TestCase):
    def test_valid_path_within_base(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            result = _safe_path(base / "child.txt", base)
            self.assertTrue(str(result).startswith(str(base.resolve())))

    def test_raises_on_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td) / "sub"
            base.mkdir()
            with self.assertRaises(ValueError):
                _safe_path(base / ".." / ".." / "escape.txt", base)


class TestFixSlugsMain(unittest.TestCase):
    def test_no_posts_file_returns_early(self):
        """main() exits early and prints a message when posts_data.json doesn't exist."""
        from devto_mirror.tools import fix_slugs

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            with _chdir(root), patch("builtins.print") as mock_print:
                fix_slugs.main()
            mock_print.assert_called_once()
            self.assertIn("Nothing to fix", mock_print.call_args[0][0])

    def test_json_load_error_returns_early(self):
        """main() exits early when posts_data.json contains invalid JSON."""
        from devto_mirror.tools import fix_slugs

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text("not valid json", encoding="utf-8")
            with _chdir(root), patch("builtins.print") as mock_print:
                fix_slugs.main()
            all_printed = " ".join(str(call) for call in mock_print.call_args_list)
            self.assertIn("Error", all_printed)

    def test_backup_created_when_missing(self):
        """main() creates a backup file when one doesn't already exist."""
        from devto_mirror.tools import fix_slugs

        posts = [{"title": "A", "link": "https://dev.to/user/my-post-123", "slug": "my-post"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root), patch("builtins.print"):
                fix_slugs.main()
            self.assertTrue((root / "posts_data.json.backup").exists())

    def test_backup_not_recreated_when_existing(self):
        """main() does not overwrite an existing backup file."""
        from devto_mirror.tools import fix_slugs

        posts = [{"title": "A", "link": "https://dev.to/user/my-post-123", "slug": "my-post"}]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            (root / "posts_data.json.backup").write_text("original backup", encoding="utf-8")
            with _chdir(root), patch("builtins.print"):
                fix_slugs.main()
            self.assertEqual((root / "posts_data.json.backup").read_text(), "original backup")

    def test_no_slugs_to_fix_prints_message(self):
        """main() prints 'No slugs needed fixing' when all slugs are already correct."""
        from devto_mirror.tools import fix_slugs

        posts = [
            {"title": "A", "link": "https://dev.to/user/my-post-123", "slug": "my-post-123"},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root), patch("builtins.print") as mock_print:
                fix_slugs.main()
            all_printed = " ".join(str(call) for call in mock_print.call_args_list)
            self.assertIn("No slugs needed fixing", all_printed)

    def test_slugs_are_fixed_and_saved(self):
        """main() fixes a wrong slug and saves the updated file."""
        from devto_mirror.tools import fix_slugs

        posts = [
            {"title": "A", "link": "https://dev.to/user/correct-slug-123", "slug": "wrong-slug"},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root), patch("builtins.print"):
                fix_slugs.main()
            updated = json.loads((root / "posts_data.json").read_text(encoding="utf-8"))
            self.assertEqual(updated[0]["slug"], "correct-slug-123")

    def test_save_error_prints_message(self):
        """main() prints an error message when the save operation fails."""
        from devto_mirror.tools import fix_slugs

        # Post with wrong slug so fixed_count > 0, which triggers the save path
        posts = [
            {"title": "A", "link": "https://dev.to/user/correct-slug-123", "slug": "wrong-slug"},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with (
                _chdir(root),
                patch("builtins.print") as mock_print,
                patch("devto_mirror.tools.fix_slugs.json.dump", side_effect=Exception("Disk full")),
            ):
                fix_slugs.main()
            all_printed = " ".join(str(call) for call in mock_print.call_args_list)
            self.assertIn("Error", all_printed)

    def test_post_with_no_link_slug_unchanged(self):
        """main() skips posts with no link and leaves their slugs unchanged."""
        from devto_mirror.tools import fix_slugs

        posts = [
            {"title": "B", "link": "", "slug": "unchanged"},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")
            with _chdir(root), patch("builtins.print"):
                fix_slugs.main()
            updated = json.loads((root / "posts_data.json").read_text(encoding="utf-8"))
            self.assertEqual(updated[0]["slug"], "unchanged")


if __name__ == "__main__":
    unittest.main()
