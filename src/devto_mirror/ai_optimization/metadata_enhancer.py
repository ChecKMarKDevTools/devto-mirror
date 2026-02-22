"""
Metadata Enhancement Module for AI Optimization

This module provides metadata enhancement capabilities for Dev.to mirror sites,
adding AI-specific meta tags while preserving existing OpenGraph, Twitter Card,
and LinkedIn meta tags from current templates.
"""

import hashlib
import logging
import re
from typing import Any, Dict

# Configure logging
logger = logging.getLogger(__name__)

DEVTO_DOMAIN = "dev.to"


class DevToMetadataEnhancer:
    """
    Metadata enhancer for Dev.to mirror sites.

    Adds AI-specific meta tags while preserving all existing OpenGraph,
    Twitter Card, and LinkedIn meta tags from current templates.
    """

    CONTENT_TYPE_TAGS = {
        "tutorial": ["tutorial", "howto", "guide", "walkthrough", "beginners"],
        "discussion": ["discuss", "discussion", "watercooler", "community", "opinion", "thoughts"],
        "career": ["career", "job", "interview", "workplace", "professional"],
        "writing": ["writing", "writers", "blogging", "content"],
        "technology": ["technology", "tooling", "tools", "vscode", "webdev"],
        "ai": ["ai", "githubcopilot", "chatgpt", "machinelearning", "ml"],
        "productivity": ["productivity", "workflow", "automation", "efficiency"],
        "challenge": ["devchallenge", "challenge", "contest", "hackathon"],
        "wellness": ["mentalhealth", "wellness", "burnout", "health"],
    }

    COMMENT_ENGAGEMENT_WEIGHT = 2

    def __init__(self, site_name: str = "ChecKMarK Dev.to Mirror", site_url: str = ""):
        """
        Initialize metadata enhancer with site information.

        Args:
            site_name: Name of the mirror site
            site_url: Base URL of the mirror site
        """
        self.site_name = site_name
        self.site_url = site_url.rstrip("/")

    def enhance_post_metadata(self, post: Any) -> Dict[str, str]:
        """
        Generate enhanced metadata dictionary for a blog post.

        Args:
            post: Post object containing article data

        Returns:
            Dictionary of meta tag name/content pairs for AI optimization
        """
        metadata = {}

        # Add article-specific meta tags
        metadata.update(self._add_article_meta_tags(post))

        # Add AI-specific meta tags
        metadata = self.add_ai_specific_tags(metadata)

        # Add source attribution metadata
        metadata.update(self.add_source_attribution_metadata(post))

        # Add content fingerprint
        content_fingerprint = self.generate_content_fingerprint(post)
        if content_fingerprint:
            metadata["content-fingerprint"] = content_fingerprint

        return metadata

    def _add_article_meta_tags(self, post: Any) -> Dict[str, str]:
        """
        Add article-specific meta tags (article:author, article:published_time, etc.).

        Args:
            post: Post object containing article data

        Returns:
            Dictionary of article meta tags
        """
        metadata = {}
        api_data = getattr(post, "api_data", {}) or {}

        author_name = self._extract_author_name(post, api_data)
        if author_name:
            metadata["article:author"] = author_name

        published_date = self._extract_published_date(post, api_data)
        if published_date:
            metadata["article:published_time"] = self._ensure_iso_timezone(published_date)

        edited_date = api_data.get("edited_at")
        if edited_date:
            metadata["article:modified_time"] = self._ensure_iso_timezone(edited_date)

        content_type = self._determine_content_type(post)
        if content_type:
            metadata["content-type"] = content_type

        return metadata

    def _extract_author_name(self, post: Any, api_data: Dict[str, Any]) -> str:
        """Extract author name from post or API data."""
        author_name = getattr(post, "author", "")
        if author_name:
            return author_name

        user_data = api_data.get("user", {})
        if user_data:
            return user_data.get("name", user_data.get("username", ""))
        return ""

    def _extract_published_date(self, post: Any, api_data: Dict[str, Any]) -> str:
        """Extract published date from post or API data."""
        published_date = getattr(post, "date", "")
        if published_date:
            return published_date
        return api_data.get("published_at", "")

    def _ensure_iso_timezone(self, date_str: str) -> str:
        """
        Ensure date string has timezone suffix.

        Args:
            date_str: Date string to normalize

        Returns:
            Normalized date string with timezone, or empty string if invalid
        """
        if not isinstance(date_str, str) or not date_str:
            return ""
        if date_str.endswith("Z") or "+" in date_str:
            return date_str
        if "T" in date_str:
            return date_str + "Z"
        return date_str

    def _determine_content_type(self, post: Any) -> str:
        """
        Determine the content type of the post based on tags and content.

        Args:
            post: Post object to analyze

        Returns:
            String indicating content type (tutorial, article, discussion, etc.)
        """
        tags_lower = self._extract_tags_lowercase(post)

        for content_type, type_tags in self.CONTENT_TYPE_TAGS.items():
            if self._has_matching_tag(tags_lower, type_tags):
                return content_type

        return "article"

    def _extract_tags_lowercase(self, post: Any) -> list[str]:
        """
        Extract tags from post and convert to lowercase.

        Args:
            post: Post object to extract tags from

        Returns:
            List of lowercase tag strings
        """
        tags = getattr(post, "tags", [])
        if not tags:
            api_data = getattr(post, "api_data", {})
            if api_data:
                tags = api_data.get("tags", [])

        if not isinstance(tags, list):
            return []

        return [tag.lower() for tag in tags if isinstance(tag, str)]

    def _has_matching_tag(self, tags_lower: list[str], type_tags: list[str]) -> bool:
        """
        Check if any tag matches the content type tags.

        Args:
            tags_lower: List of lowercase tags from post
            type_tags: List of tags that identify a content type

        Returns:
            True if any tag matches, False otherwise
        """
        return any(tag in tags_lower for tag in type_tags)

    def add_ai_specific_tags(self, metadata: Dict[str, str]) -> Dict[str, str]:
        """
        Add AI-specific meta tags to existing metadata.

        Args:
            metadata: Existing metadata dictionary

        Returns:
            Enhanced metadata with AI-specific tags added
        """
        # Add robots meta tag with AI-friendly directives
        metadata["robots"] = "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"

        # Add content language (default to English)
        if "content-language" not in metadata:
            metadata["content-language"] = "en"

        # Add generator information
        metadata["generator"] = f"{self.site_name} AI-Optimized Mirror"

        # Add referrer policy for better privacy
        metadata["referrer"] = "strict-origin-when-cross-origin"

        # Add theme color if not present
        if "theme-color" not in metadata:
            metadata["theme-color"] = "#000000"

        return metadata

    def generate_content_fingerprint(self, post: Any) -> str:
        """
        Generate unique content identifier for the post.

        Args:
            post: Post object to fingerprint

        Returns:
            Unique string identifier for content tracking
        """
        # Collect identifying information
        fingerprint_data = []

        # Add title
        title = getattr(post, "title", "")
        if title:
            fingerprint_data.append(f"title:{title}")

        # Add publication date
        date = getattr(post, "date", "")
        if not date:
            api_data = getattr(post, "api_data", {})
            if api_data:
                date = api_data.get("published_at", "")
        if date:
            fingerprint_data.append(f"date:{date}")

        # Add Dev.to URL if available
        link = getattr(post, "link", "")
        if link:
            fingerprint_data.append(f"source:{link}")

        # Add content hash (first 100 characters of content)
        content = getattr(post, "content_html", "") or getattr(post, "content", "")
        if content:
            # Remove HTML tags for cleaner hash
            clean_content = re.sub(r"<[^>]+>", "", content)
            content_sample = clean_content[:100].strip()
            if content_sample:
                fingerprint_data.append(f"content:{content_sample}")

        # Add author information for uniqueness
        api_data = getattr(post, "api_data", {})
        if api_data and "user" in api_data:
            username = api_data["user"].get("username", "")
            if username:
                fingerprint_data.append(f"author:{username}")

        # Create hash from combined data
        if fingerprint_data:
            combined_data = "|".join(fingerprint_data)
            hash_object = hashlib.sha256(combined_data.encode("utf-8"))
            return hash_object.hexdigest()[:16]  # Use first 16 characters

        return ""

    def add_source_attribution_metadata(self, post: Any) -> Dict[str, str]:
        """
        Add Dev.to source attribution meta tags and canonical link validation.

        Args:
            post: Post object with Dev.to source information

        Returns:
            Dictionary of source attribution meta tags
        """
        metadata = {}

        canonical_url = getattr(post, "link", "")
        if canonical_url:
            metadata.update(self._build_canonical_metadata(canonical_url))

        api_data = getattr(post, "api_data", {}) or {}
        if api_data:
            metadata.update(self._build_api_metadata(api_data))

        return metadata

    def _build_canonical_metadata(self, canonical_url: str) -> Dict[str, str]:
        """Build metadata from canonical URL."""
        metadata = {"canonical": canonical_url}

        if not self._validate_devto_canonical_url(canonical_url):
            return metadata

        metadata["source-platform"] = DEVTO_DOMAIN
        metadata["source-url"] = canonical_url

        username = self._extract_username_from_devto_url(canonical_url)
        if username:
            metadata["source-author-profile"] = f"https://dev.to/{username}"

        return metadata

    def _build_api_metadata(self, api_data: Dict[str, Any]) -> Dict[str, str]:
        """Build metadata from API data."""
        metadata = {}

        post_id = api_data.get("id")
        if post_id:
            metadata["source-post-id"] = str(post_id)

        published_at = api_data.get("published_at")
        if published_at:
            metadata["original-published-date"] = published_at

        reading_time = api_data.get("reading_time_minutes")
        if reading_time and reading_time > 0:
            metadata["reading-time"] = f"{reading_time} minutes"

        self._add_engagement_metrics(metadata, api_data)

        return metadata

    def _add_engagement_metrics(self, metadata: Dict[str, str], api_data: Dict[str, Any]) -> None:
        """
        Add engagement metrics to metadata dictionary (modifies in-place).

        Args:
            metadata: Dictionary to update with engagement metrics
            api_data: API data containing engagement metrics

        Side Effects:
            Modifies metadata dict by adding devto:reactions, devto:comments,
            devto:page_views, and devto:engagement_score keys
        """
        metric_mappings = [
            ("public_reactions_count", "devto:reactions"),
            ("comments_count", "devto:comments"),
            ("page_views_count", "devto:page_views"),
        ]

        for api_key, meta_key in metric_mappings:
            value = api_data.get(api_key)
            if value is not None and value >= 0:
                metadata[meta_key] = str(value)

        reactions = api_data.get("public_reactions_count")
        comments = api_data.get("comments_count")
        if reactions is not None and comments is not None:
            engagement_score = reactions + (comments * self.COMMENT_ENGAGEMENT_WEIGHT)
            metadata["devto:engagement_score"] = str(engagement_score)

    def _validate_devto_canonical_url(self, url: str) -> bool:
        """
        Validate that the canonical URL is a proper Dev.to URL.

        Args:
            url: URL to validate

        Returns:
            True if valid Dev.to URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Check if it's a Dev.to URL
        return DEVTO_DOMAIN in url.lower() and url.startswith(("http://", "https://"))

    def _extract_username_from_devto_url(self, url: str) -> str:
        """
        Extract username from Dev.to URL pattern.

        Args:
            url: Dev.to URL (e.g., https://dev.to/username/post-slug)

        Returns:
            Username string, or empty string if extraction fails
        """
        try:
            if not url or DEVTO_DOMAIN not in url:
                return ""

            # Split URL and extract username
            # Expected format: https://dev.to/username/post-slug
            url_parts = url.split("/")
            if len(url_parts) >= 4 and DEVTO_DOMAIN in url:
                username = url_parts[3]  # Username should be at index 3
                # Basic validation - username shouldn't be empty or contain special chars
                if username and username.replace("-", "").replace("_", "").isalnum():
                    return username

        except Exception as e:
            logger.debug(f"Failed to extract username from URL {url}: {e}")

        return ""
