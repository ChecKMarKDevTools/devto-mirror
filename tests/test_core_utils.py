"""Tests for devto_mirror.core.utils"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import devto_mirror.core.utils as utils_module


class TestGetPostTemplate(unittest.TestCase):
    def test_returns_a_template(self):
        """get_post_template() should always return a renderable template."""
        tmpl = utils_module.get_post_template()
        self.assertIsNotNone(tmpl)

    def test_fallback_on_get_template_exception(self):
        """When env.get_template raises, the inline fallback template is returned."""
        with (
            patch.object(utils_module, "template_dir") as mock_td,
            patch.object(utils_module.env, "get_template", side_effect=Exception("Not found")),
        ):
            mock_td.exists.return_value = True
            tmpl = utils_module.get_post_template()
        self.assertIsNotNone(tmpl)
        # Fallback template is from_string; can render with minimal vars
        rendered = tmpl.render(
            title="T",
            canonical="https://x.com",
            description="D",
            date="",
            content="",
            cover_image="",
            tags=[],
            social_image="",
            site_name="S",
            author="A",
            enhanced_metadata={},
            json_ld_schemas=[],
            cross_references=None,
        )
        self.assertIn("T", rendered)


class TestParseDate(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(utils_module.parse_date(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(utils_module.parse_date(""))

    def test_iso_string_with_z_suffix(self):
        result = utils_module.parse_date("2024-01-01T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)

    def test_iso_string_without_z_suffix(self):
        """ISO string without Z suffix hits _parse_iso_date_str line 241."""
        result = utils_module.parse_date("2024-06-15T12:00:00+00:00")
        self.assertIsNotNone(result)

    def test_iso_string_no_timezone_gets_utc(self):
        """Plain ISO string (no tz) should be given UTC tzinfo."""
        result = utils_module.parse_date("2024-01-15T10:30:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_datetime_object_tz_aware(self):
        """Passing a tz-aware datetime returns it unchanged (lines 252-257)."""
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = utils_module.parse_date(dt)
        self.assertEqual(result, dt)

    def test_datetime_object_naive_gets_utc(self):
        """Naive datetime object gets UTC tzinfo attached."""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        self.assertIsNone(dt.tzinfo)
        result = utils_module.parse_date(dt)
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.year, 2024)

    def test_float_unix_timestamp(self):
        """Float unix timestamp is converted to datetime (lines 259-266)."""
        result = utils_module.parse_date(1704067200.0)  # 2024-01-01T00:00:00 UTC
        self.assertIsNotNone(result)
        self.assertIsInstance(result, datetime)
        self.assertIsNotNone(result.tzinfo)

    def test_int_unix_timestamp(self):
        """Integer unix timestamp is also supported."""
        result = utils_module.parse_date(1704067200)
        self.assertIsNotNone(result)

    def test_invalid_string_returns_none(self):
        result = utils_module.parse_date("not-a-date")
        self.assertIsNone(result)

    def test_unparseable_float_returns_none(self):
        """Astronomically large float raises OverflowError → returns None."""
        result = utils_module.parse_date(float("inf"))
        self.assertIsNone(result)


class TestPostIdentityKey(unittest.TestCase):
    def test_post_with_id_returns_id_key(self):
        post = {"id": 123, "link": "https://example.com/post"}
        result = utils_module._post_identity_key(post)
        self.assertEqual(result, "id:123")

    def test_post_with_api_data_id(self):
        post = {"api_data": {"id": 456}, "link": "https://example.com/post"}
        result = utils_module._post_identity_key(post)
        self.assertEqual(result, "id:456")

    def test_post_id_zero_falls_back_to_link(self):
        post = {"id": 0, "link": "https://example.com/post"}
        result = utils_module._post_identity_key(post)
        self.assertEqual(result, "link:https://example.com/post")

    def test_post_with_no_id_uses_link(self):
        post = {"link": "https://example.com/post"}
        result = utils_module._post_identity_key(post)
        self.assertEqual(result, "link:https://example.com/post")

    def test_link_with_trailing_slash_stripped(self):
        post = {"link": "https://example.com/post/"}
        result = utils_module._post_identity_key(post)
        self.assertEqual(result, "link:https://example.com/post")

    def test_post_with_no_id_and_no_link_returns_none(self):
        post = {"title": "No identity key"}
        result = utils_module._post_identity_key(post)
        self.assertIsNone(result)

    def test_invalid_id_falls_back_to_link(self):
        post = {"id": "not-an-int", "link": "https://example.com/post"}
        result = utils_module._post_identity_key(post)
        # "not-an-int" raises ValueError in int(), so post_id=0 → uses link
        self.assertEqual(result, "link:https://example.com/post")


class TestPostActivityDt(unittest.TestCase):
    def test_uses_most_recent_date(self):
        post = {
            "api_data": {
                "edited_at": "2024-01-05T00:00:00Z",
                "published_at": "2024-01-01T00:00:00Z",
            }
        }
        result = utils_module._post_activity_dt(post)
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.day, 5)

    def test_uses_top_level_date_field(self):
        post = {"date": "2024-03-15T10:00:00Z"}
        result = utils_module._post_activity_dt(post)
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 3)

    def test_uses_edited_at_over_published(self):
        post = {
            "edited_at": "2024-06-01T00:00:00Z",
            "published_at": "2024-01-01T00:00:00Z",
        }
        result = utils_module._post_activity_dt(post)
        self.assertEqual(result.month, 6)

    def test_all_candidates_none_returns_none(self):
        post = {"title": "No dates at all"}
        result = utils_module._post_activity_dt(post)
        self.assertIsNone(result)

    def test_non_dict_api_data_ignored(self):
        post = {"api_data": "not-a-dict", "date": "2024-01-01T00:00:00Z"}
        result = utils_module._post_activity_dt(post)
        self.assertIsNotNone(result)


class TestMergePostDicts(unittest.TestCase):
    def test_primary_wins_on_conflicts(self):
        primary = {"title": "Primary Title", "description": "Primary desc"}
        secondary = {"title": "Secondary Title", "description": "Secondary desc"}
        result = utils_module._merge_post_dicts(primary=primary, secondary=secondary)
        self.assertEqual(result["title"], "Primary Title")
        self.assertEqual(result["description"], "Primary desc")

    def test_missing_primary_fields_filled_from_secondary(self):
        primary = {"title": "Primary Title"}
        secondary = {"title": "Secondary", "description": "Sec desc", "slug": "sec-slug"}
        result = utils_module._merge_post_dicts(primary=primary, secondary=secondary)
        self.assertEqual(result["title"], "Primary Title")
        self.assertEqual(result["description"], "Sec desc")
        self.assertEqual(result["slug"], "sec-slug")

    def test_api_data_merged_with_primary_wins(self):
        primary = {"api_data": {"id": 1, "title": "Primary"}}
        secondary = {"api_data": {"id": 2, "description": "Sec desc"}}
        result = utils_module._merge_post_dicts(primary=primary, secondary=secondary)
        # Primary api_data wins on conflict; missing fields pulled from secondary
        self.assertEqual(result["api_data"]["id"], 1)
        self.assertEqual(result["api_data"]["description"], "Sec desc")

    def test_non_dict_api_data_treated_as_empty(self):
        primary = {"api_data": "not-a-dict", "title": "P"}
        secondary = {"api_data": {"extra": "value"}, "title": "S"}
        result = utils_module._merge_post_dicts(primary=primary, secondary=secondary)
        # api_data from secondary is used since primary's is not a dict
        self.assertEqual(result["api_data"]["extra"], "value")


class TestPostDateSortKey(unittest.TestCase):
    def test_returns_activity_dt_when_available(self):
        post = {"date": "2024-06-01T00:00:00Z"}
        result = utils_module._post_date_sort_key(post)
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 6)

    def test_returns_min_datetime_fallback_when_no_date(self):
        post = {"title": "No dates"}
        result = utils_module._post_date_sort_key(post)
        fallback = datetime.min.replace(tzinfo=timezone.utc)
        self.assertEqual(result, fallback)


class TestDedupePostsByLink(unittest.TestCase):
    def test_empty_list_returns_empty(self):
        result = utils_module.dedupe_posts_by_link([])
        self.assertEqual(result, [])

    def test_non_dict_items_skipped(self):
        posts = [
            "not-a-dict",
            {"id": 1, "link": "https://example.com/post", "date": "2024-01-01T00:00:00Z"},
            42,
        ]
        result = utils_module.dedupe_posts_by_link(posts)
        self.assertEqual(len(result), 1)

    def test_posts_with_no_identity_key_skipped(self):
        posts = [
            {"title": "No link no id"},
            {"id": 1, "link": "https://example.com/post"},
        ]
        result = utils_module.dedupe_posts_by_link(posts)
        self.assertEqual(len(result), 1)

    def test_deduplication_by_id(self):
        older = {
            "id": 123,
            "link": "https://example.com/post",
            "api_data": {"id": 123, "edited_at": "2024-01-01T00:00:00Z"},
        }
        newer = {
            "id": 123,
            "link": "https://example.com/post",
            "title": "Updated",
            "api_data": {"id": 123, "edited_at": "2024-01-05T00:00:00Z"},
        }
        result = utils_module.dedupe_posts_by_link([older, newer])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Updated")

    def test_existing_stays_primary_when_incoming_older(self):
        """When existing is newer, merge keeps existing as primary but backfills missing fields."""
        newer_existing = {
            "id": 1,
            "link": "https://example.com/post",
            "title": "Existing Newer",
            "api_data": {"id": 1, "edited_at": "2024-01-05T00:00:00Z"},
        }
        older_incoming = {
            "id": 1,
            "link": "https://example.com/post",
            "description": "Old desc",
            "api_data": {"id": 1, "edited_at": "2024-01-01T00:00:00Z"},
        }
        result = utils_module.dedupe_posts_by_link([newer_existing, older_incoming])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Existing Newer")
        self.assertEqual(result[0]["description"], "Old desc")

    def test_post_with_to_dict_method_used(self):
        """Post objects with to_dict() are converted before processing."""

        class PostObj:
            def to_dict(self):
                return {
                    "id": 5,
                    "link": "https://example.com/post-5",
                    "date": "2024-01-01T00:00:00Z",
                    "api_data": {"id": 5},
                }

        result = utils_module.dedupe_posts_by_link([PostObj()])
        self.assertEqual(len(result), 1)

    def test_sorted_newest_first(self):
        posts = [
            {"id": 1, "link": "https://example.com/old", "date": "2024-01-01T00:00:00Z"},
            {"id": 2, "link": "https://example.com/new", "date": "2024-01-03T00:00:00Z"},
            {"id": 3, "link": "https://example.com/mid", "date": "2024-01-02T00:00:00Z"},
        ]
        result = utils_module.dedupe_posts_by_link(posts)
        self.assertEqual(len(result), 3)
        # First item should be newest
        activity_0 = utils_module._post_activity_dt(result[0])
        activity_1 = utils_module._post_activity_dt(result[1])
        self.assertGreaterEqual(activity_0, activity_1)


if __name__ == "__main__":
    unittest.main()
