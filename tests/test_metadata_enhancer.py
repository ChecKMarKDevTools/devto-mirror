"""
Tests for the Metadata Enhancer module.
"""

import unittest
from unittest.mock import Mock

from devto_mirror.ai_optimization import DevToMetadataEnhancer


class TestDevToMetadataEnhancer(unittest.TestCase):
    """Test cases for DevToMetadataEnhancer."""

    def setUp(self):
        """Set up test fixtures."""
        self.enhancer = DevToMetadataEnhancer("Test Site", "https://example.com")

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        enhancer = DevToMetadataEnhancer()
        self.assertEqual(enhancer.site_name, "ChecKMarK Dev.to Mirror")
        self.assertEqual(enhancer.site_url, "")

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        enhancer = DevToMetadataEnhancer("Custom Site", "https://custom.com/")
        self.assertEqual(enhancer.site_name, "Custom Site")
        self.assertEqual(enhancer.site_url, "https://custom.com")  # Should strip trailing slash

    def test_enhance_post_metadata_basic(self):
        """Test basic post metadata enhancement."""
        mock_post = Mock()
        mock_post.configure_mock(
            **{
                "title": "Test Article",
                "date": "2023-01-01T12:00:00",
                "author": "Test Author",
                "tags": ["python", "tutorial"],
                "link": "https://dev.to/testuser/test-article",
                "content_html": "<p>Test content with some words here.</p>",
                "api_data": {},
            }
        )

        metadata = self.enhancer.enhance_post_metadata(mock_post)

        # Check article meta tags
        self.assertEqual(metadata["article:author"], "Test Author")
        self.assertEqual(metadata["article:published_time"], "2023-01-01T12:00:00Z")
        self.assertEqual(metadata["content-type"], "tutorial")

        # Check AI-specific tags
        self.assertIn("robots", metadata)
        self.assertEqual(metadata["content-language"], "en")
        self.assertEqual(metadata["generator"], "Test Site AI-Optimized Mirror")
        self.assertEqual(metadata["referrer"], "strict-origin-when-cross-origin")
        self.assertEqual(metadata["theme-color"], "#000000")

        # Check source attribution
        self.assertEqual(metadata["canonical"], "https://dev.to/testuser/test-article")
        self.assertEqual(metadata["source-platform"], "dev.to")
        self.assertEqual(metadata["source-url"], "https://dev.to/testuser/test-article")
        self.assertEqual(metadata["source-author-profile"], "https://dev.to/testuser")

        # Check content fingerprint
        self.assertIn("content-fingerprint", metadata)
        self.assertEqual(len(metadata["content-fingerprint"]), 16)

    def test_enhance_post_metadata_with_api_data(self):
        """Test post metadata enhancement with API data."""
        api_data = {
            "user": {"name": "John Doe", "username": "johndoe"},
            "published_at": "2023-01-01T12:00:00Z",
            "edited_at": "2023-01-02T12:00:00Z",
            "tags": ["javascript", "webdev"],
            "reading_time_minutes": 5,
            "public_reactions_count": 42,
            "comments_count": 10,
            "id": 12345,
        }

        mock_post = Mock()
        mock_post.configure_mock(
            **{
                "title": "Test Article",
                "author": "",
                "date": "",
                "tags": [],
                "link": "https://dev.to/johndoe/test-article",
                "content_html": "<p>Test content</p>",
                "api_data": api_data,
            }
        )

        metadata = self.enhancer.enhance_post_metadata(mock_post)

        # Check API data is used
        self.assertEqual(metadata["article:author"], "John Doe")
        self.assertEqual(metadata["article:published_time"], "2023-01-01T12:00:00Z")
        self.assertEqual(metadata["article:modified_time"], "2023-01-02T12:00:00Z")
        self.assertEqual(metadata["source-post-id"], "12345")
        self.assertEqual(metadata["original-published-date"], "2023-01-01T12:00:00Z")
        self.assertEqual(metadata["reading-time"], "5 minutes")
        self.assertEqual(metadata["devto:reactions"], "42")
        self.assertEqual(metadata["devto:comments"], "10")
        self.assertEqual(metadata["devto:engagement_score"], "62")

    def test_determine_content_type(self):
        """Test content type determination based on tags."""
        test_cases = [
            (["tutorial", "python"], "tutorial"),
            (["discuss", "career"], "discussion"),
            (["career", "interview"], "career"),
            (["writing", "blogging"], "writing"),
            (["technology", "vscode"], "technology"),
            (["ai", "githubcopilot"], "ai"),
            (["productivity", "workflow"], "productivity"),
            (["devchallenge", "hackathon"], "challenge"),
            (["mentalhealth", "wellness"], "wellness"),
            (["random", "other"], "article"),
            ([], "article"),
        ]

        for tags, expected_type in test_cases:
            with self.subTest(tags=tags):
                mock_post = Mock()
                mock_post.configure_mock(**{"tags": tags})

                result = self.enhancer._determine_content_type(mock_post)
                self.assertEqual(result, expected_type)

    def test_determine_content_type_from_api_data(self):
        """Test content type determination from API data when post tags are empty."""
        api_data = {"tags": ["tutorial", "beginners"]}

        mock_post = Mock()
        mock_post.configure_mock(**{"tags": [], "api_data": api_data})

        result = self.enhancer._determine_content_type(mock_post)
        self.assertEqual(result, "tutorial")

    def test_add_ai_specific_tags(self):
        """Test adding AI-specific meta tags."""
        existing_metadata = {"description": "Test description"}

        enhanced = self.enhancer.add_ai_specific_tags(existing_metadata)

        # Check existing metadata is preserved
        self.assertEqual(enhanced["description"], "Test description")

        # Check AI-specific tags are added
        self.assertEqual(
            enhanced["robots"], "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"
        )
        self.assertEqual(enhanced["content-language"], "en")
        self.assertEqual(enhanced["generator"], "Test Site AI-Optimized Mirror")
        self.assertEqual(enhanced["referrer"], "strict-origin-when-cross-origin")
        self.assertEqual(enhanced["theme-color"], "#000000")

    def test_add_ai_specific_tags_preserves_existing(self):
        """Test that AI-specific tags don't override existing values."""
        existing_metadata = {
            "content-language": "es",
            "theme-color": "#ff0000",
        }

        enhanced = self.enhancer.add_ai_specific_tags(existing_metadata)

        # Check existing values are preserved
        self.assertEqual(enhanced["content-language"], "es")
        self.assertEqual(enhanced["theme-color"], "#ff0000")

    def test_generate_content_fingerprint(self):
        """Test content fingerprint generation."""
        mock_post = Mock()
        mock_post.configure_mock(
            **{
                "title": "Test Article",
                "date": "2023-01-01",
                "link": "https://dev.to/user/test",
                "content_html": "<p>This is test content with some words</p>",
                "api_data": {"user": {"username": "testuser"}},
            }
        )

        fingerprint = self.enhancer.generate_content_fingerprint(mock_post)

        # Should return a 16-character hex string
        self.assertEqual(len(fingerprint), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in fingerprint))

    def test_generate_content_fingerprint_empty_post(self):
        """Test content fingerprint generation with empty post."""
        mock_post = Mock()
        mock_post.configure_mock(
            **{
                "title": "",
                "date": "",
                "link": "",
                "content_html": "",
                "content": "",
                "api_data": {},
            }
        )

        fingerprint = self.enhancer.generate_content_fingerprint(mock_post)
        self.assertEqual(fingerprint, "")

    def test_validate_devto_canonical_url(self):
        """Test Dev.to canonical URL validation."""
        valid_urls = [
            "https://dev.to/user/post-slug",
            "https://dev.to/user/post-slug-123",
        ]

        invalid_urls = [
            "",
            None,
            "https://example.com/post",
            "not-a-url",
            "ftp://dev.to/user/post",
            "http://dev.to/user/post-slug",
        ]

        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.enhancer._validate_devto_canonical_url(url))

        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.enhancer._validate_devto_canonical_url(url))

    def test_extract_username_from_devto_url(self):
        """Test username extraction from Dev.to URLs."""
        test_cases = [
            ("https://dev.to/johndoe/my-post-slug", "johndoe"),
            ("https://dev.to/user_name/another-post", "user_name"),
            ("https://dev.to/user-123/post-title", "user-123"),
            ("https://dev.to/", ""),
            ("https://example.com/user/post", ""),
            ("", ""),
            ("not-a-url", ""),
        ]

        for url, expected_username in test_cases:
            with self.subTest(url=url):
                result = self.enhancer._extract_username_from_devto_url(url)
                self.assertEqual(result, expected_username)

    def test_add_source_attribution_metadata(self):
        """Test source attribution metadata generation."""
        api_data = {
            "id": 12345,
            "published_at": "2023-01-01T12:00:00Z",
            "reading_time_minutes": 5,
            "public_reactions_count": 42,
            "comments_count": 10,
        }

        mock_post = Mock()
        mock_post.configure_mock(
            **{
                "link": "https://dev.to/testuser/my-post",
                "api_data": api_data,
            }
        )

        metadata = self.enhancer.add_source_attribution_metadata(mock_post)

        self.assertEqual(metadata["canonical"], "https://dev.to/testuser/my-post")
        self.assertEqual(metadata["source-platform"], "dev.to")
        self.assertEqual(metadata["source-url"], "https://dev.to/testuser/my-post")
        self.assertEqual(metadata["source-author-profile"], "https://dev.to/testuser")
        self.assertEqual(metadata["source-post-id"], "12345")
        self.assertEqual(metadata["original-published-date"], "2023-01-01T12:00:00Z")
        self.assertEqual(metadata["reading-time"], "5 minutes")
        self.assertEqual(metadata["devto:reactions"], "42")
        self.assertEqual(metadata["devto:comments"], "10")
        self.assertEqual(metadata["devto:engagement_score"], "62")

    def test_add_source_attribution_metadata_no_api_data(self):
        """Test source attribution metadata with no API data."""
        mock_post = Mock()
        mock_post.configure_mock(
            **{
                "link": "https://dev.to/testuser/my-post",
                "api_data": {},
            }
        )

        metadata = self.enhancer.add_source_attribution_metadata(mock_post)

        # Should still have basic attribution
        self.assertEqual(metadata["canonical"], "https://dev.to/testuser/my-post")
        self.assertEqual(metadata["source-platform"], "dev.to")
        self.assertEqual(metadata["source-url"], "https://dev.to/testuser/my-post")
        self.assertEqual(metadata["source-author-profile"], "https://dev.to/testuser")

        # Should not have API-specific fields
        self.assertNotIn("source-post-id", metadata)
        self.assertNotIn("original-published-date", metadata)
        self.assertNotIn("reading-time", metadata)
        self.assertNotIn("devto:reactions", metadata)
        self.assertNotIn("devto:comments", metadata)
        self.assertNotIn("devto:engagement_score", metadata)

    def test_ensure_iso_timezone_edge_cases(self):
        """Test _ensure_iso_timezone with edge cases."""
        self.assertEqual(self.enhancer._ensure_iso_timezone(""), "")
        self.assertEqual(self.enhancer._ensure_iso_timezone(None), "")
        self.assertEqual(self.enhancer._ensure_iso_timezone("2023-01-01"), "2023-01-01")
        self.assertEqual(self.enhancer._ensure_iso_timezone("2023-01-01T12:00:00Z"), "2023-01-01T12:00:00Z")
        self.assertEqual(self.enhancer._ensure_iso_timezone("2023-01-01T12:00:00+05:00"), "2023-01-01T12:00:00+05:00")

    def test_extract_author_name_no_user_data(self):
        """Test _extract_author_name when user data is empty."""
        mock_post = Mock()
        mock_post.author = ""
        result = self.enhancer._extract_author_name(mock_post, {})
        self.assertEqual(result, "")

    def test_build_canonical_metadata_non_devto_url(self):
        """Test _build_canonical_metadata with non-dev.to URL."""
        result = self.enhancer._build_canonical_metadata("https://example.com/post")
        self.assertEqual(result, {"canonical": "https://example.com/post"})
        self.assertNotIn("source-platform", result)

    def test_add_engagement_metrics(self):
        """Test _add_engagement_metrics calculation logic."""
        metadata = {}
        api_data = {
            "public_reactions_count": 42,
            "comments_count": 10,
            "page_views_count": 500,
        }

        self.enhancer._add_engagement_metrics(metadata, api_data)

        self.assertEqual(metadata["devto:reactions"], "42")
        self.assertEqual(metadata["devto:comments"], "10")
        self.assertEqual(metadata["devto:page_views"], "500")
        self.assertEqual(metadata["devto:engagement_score"], "62")

    def test_add_engagement_metrics_partial_data(self):
        """Test _add_engagement_metrics with partial data."""
        metadata = {}
        api_data = {"public_reactions_count": 20}

        self.enhancer._add_engagement_metrics(metadata, api_data)

        self.assertEqual(metadata["devto:reactions"], "20")
        self.assertNotIn("devto:comments", metadata)
        self.assertNotIn("devto:engagement_score", metadata)

    def test_add_engagement_metrics_zero_values(self):
        """Test _add_engagement_metrics with zero values."""
        metadata = {}
        api_data = {
            "public_reactions_count": 0,
            "comments_count": 0,
            "page_views_count": 0,
        }

        self.enhancer._add_engagement_metrics(metadata, api_data)

        self.assertEqual(metadata["devto:reactions"], "0")
        self.assertEqual(metadata["devto:comments"], "0")
        self.assertEqual(metadata["devto:page_views"], "0")
        self.assertEqual(metadata["devto:engagement_score"], "0")


if __name__ == "__main__":
    unittest.main()
