"""Tests for devto_mirror.tools.analyze_descriptions"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from devto_mirror.core.constants import (
    SEO_DESCRIPTION_LIMIT,
    SEO_DESCRIPTION_WARNING,
    STATUS_EXCEEDS_LIMIT,
    STATUS_NEAR_LIMIT,
)
from devto_mirror.tools.analyze_descriptions import (
    analyze_posts_data,
    generate_report,
    main,
    print_long_descriptions,
    print_markdown_comment,
    print_missing_descriptions,
    print_summary,
)


class TestAnalyzePostsData(unittest.TestCase):
    def test_file_not_found(self):
        long, missing = analyze_posts_data("/tmp/nonexistent_file_xyz_abc.json")
        self.assertEqual(long, [])
        self.assertEqual(missing, [])

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("not valid json at all {{{")
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(long, [])
            self.assertEqual(missing, [])
        finally:
            os.unlink(fname)

    def test_description_exceeds_warning_limit(self):
        """Description > SEO_DESCRIPTION_WARNING → STATUS_EXCEEDS_LIMIT"""
        posts = [
            {
                "title": "Long Post",
                "description": "x" * (SEO_DESCRIPTION_WARNING + 1),
                "link": "https://example.com/long",
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(long), 1)
            self.assertEqual(long[0]["status"], STATUS_EXCEEDS_LIMIT)
            self.assertEqual(len(missing), 0)
        finally:
            os.unlink(fname)

    def test_description_near_limit(self):
        """Description > SEO_DESCRIPTION_LIMIT but <= SEO_DESCRIPTION_WARNING → STATUS_NEAR_LIMIT"""
        posts = [
            {
                "title": "Near Limit Post",
                "description": "x" * (SEO_DESCRIPTION_LIMIT + 1),
                "link": "https://example.com/near",
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(long), 1)
            self.assertEqual(long[0]["status"], STATUS_NEAR_LIMIT)
        finally:
            os.unlink(fname)

    def test_description_within_limit(self):
        posts = [{"title": "A", "description": "Short description", "link": "https://example.com"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(long), 0)
            self.assertEqual(len(missing), 0)
        finally:
            os.unlink(fname)

    def test_missing_empty_description(self):
        posts = [{"title": "A", "description": "", "link": "https://example.com/a"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(missing), 1)
            self.assertEqual(len(long), 0)
        finally:
            os.unlink(fname)

    def test_missing_whitespace_only_description(self):
        posts = [{"title": "A", "description": "   ", "link": "https://example.com/a"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(missing), 1)
        finally:
            os.unlink(fname)

    def test_missing_absent_description_field(self):
        """Post without description key at all → missing descriptions"""
        posts = [{"title": "No Description", "link": "https://example.com/no-desc"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(missing), 1)
        finally:
            os.unlink(fname)

    def test_mixed_posts(self):
        posts = [
            {"title": "Long", "description": "x" * 200, "link": "https://example.com/long"},
            {"title": "Missing", "description": "", "link": "https://example.com/missing"},
            {"title": "OK", "description": "Short desc", "link": "https://example.com/ok"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with patch("builtins.print"):
                long, missing = analyze_posts_data(fname)
            self.assertEqual(len(long), 1)
            self.assertEqual(len(missing), 1)
        finally:
            os.unlink(fname)


class TestGenerateReport(unittest.TestCase):
    def test_all_ok_prints_message(self):
        """When no issues, generate_report prints an 'all OK' message."""
        with patch("builtins.print") as mock_print:
            generate_report([], [])
        all_printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("All post descriptions", all_printed)

    def test_with_long_descriptions(self):
        long = [
            {
                "title": "Long Post",
                "url": "https://example.com/long",
                "description": "x" * 200,
                "length": 200,
                "status": STATUS_EXCEEDS_LIMIT,
            }
        ]
        with patch("builtins.print"):
            generate_report(long, [])

    def test_with_missing_descriptions(self):
        missing = [{"title": "Missing", "url": "https://example.com/missing", "reason": "Empty description"}]
        with patch("builtins.print"):
            generate_report([], missing)

    def test_with_both_violations(self):
        long = [
            {
                "title": "T",
                "url": "https://example.com/t",
                "description": "x" * 200,
                "length": 200,
                "status": STATUS_EXCEEDS_LIMIT,
            }
        ]
        missing = [{"title": "M", "url": "https://example.com/m", "reason": "Empty"}]
        with patch("builtins.print"):
            generate_report(long, missing)


class TestPrintFunctions(unittest.TestCase):
    def test_print_long_descriptions_empty_list(self):
        """Empty long descriptions list → no output."""
        with patch("builtins.print") as mock_print:
            print_long_descriptions([])
        mock_print.assert_not_called()

    def test_print_long_descriptions_near_limit(self):
        """NEAR_LIMIT status uses yellow emoji."""
        item = {
            "title": "T",
            "url": "https://example.com/t",
            "description": "x" * 142,
            "length": 142,
            "status": STATUS_NEAR_LIMIT,
        }
        with patch("builtins.print") as mock_print:
            print_long_descriptions([item])
        self.assertTrue(mock_print.called)

    def test_print_missing_descriptions_empty_list(self):
        with patch("builtins.print") as mock_print:
            print_missing_descriptions([])
        mock_print.assert_not_called()

    def test_print_missing_descriptions_with_items(self):
        missing = [{"title": "M", "url": "https://example.com/m", "reason": "Empty"}]
        with patch("builtins.print") as mock_print:
            print_missing_descriptions(missing)
        self.assertTrue(mock_print.called)

    def test_print_markdown_comment_empty_both(self):
        with patch("builtins.print") as mock_print:
            print_markdown_comment([], [])
        mock_print.assert_not_called()

    def test_print_summary(self):
        with patch("builtins.print") as mock_print:
            print_summary([], [])
        self.assertTrue(mock_print.called)


class TestMain(unittest.TestCase):
    def test_main_no_file(self):
        """main() runs cleanly when the specified file doesn't exist."""
        with (
            patch.object(sys, "argv", ["analyze_descriptions.py", "/tmp/nonexistent_xyz_123.json"]),
            patch("builtins.print"),
        ):
            main()

    def test_main_defaults_to_posts_data_file(self):
        """main() uses default POSTS_DATA_FILE when no CLI arg given."""
        with patch.object(sys, "argv", ["analyze_descriptions.py"]):
            with patch("builtins.print"):
                with patch("devto_mirror.tools.analyze_descriptions.analyze_posts_data", return_value=([], [])):
                    main()

    def test_main_with_violations(self):
        posts = [
            {"title": "Long", "description": "x" * 200, "link": "https://example.com/long"},
            {"title": "Missing", "description": "", "link": "https://example.com/missing"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(posts, f)
            fname = f.name
        try:
            with (
                patch.object(sys, "argv", ["analyze_descriptions.py", fname]),
                patch("builtins.print"),
            ):
                main()
        finally:
            os.unlink(fname)


if __name__ == "__main__":
    unittest.main()
