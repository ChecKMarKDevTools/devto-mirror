"""Schema Generator Module for AI Optimization."""

import logging
import re
from typing import Any, Dict, Optional, Tuple

from .utils import validate_json_ld_schema

logger = logging.getLogger(__name__)

SCHEMA_ORG_BASE = "https://schema.org"
JSON_LD_CONTEXT = "@context"
JSON_LD_TYPE = "@type"
SCHEMA_ORG_COMMENT_ACTION = "https://schema.org/CommentAction"
SCHEMA_ORG_LIKE_ACTION = "https://schema.org/LikeAction"

INTERACTION_TYPE_MAPPING = {
    "commentCount": SCHEMA_ORG_COMMENT_ACTION,
    "interactionCount": SCHEMA_ORG_LIKE_ACTION,
}


class DevToSchemaGenerator:
    """Generate Schema.org compliant JSON-LD structured data for Dev.to mirror sites."""

    def __init__(self, site_name: str = "ChecKMarK Dev.to Mirror", site_url: str = ""):
        self.site_name = site_name
        self.site_url = site_url.rstrip("/")

    def _extract_author_info(self, canonical_url: str, api_data: Optional[Dict[str, Any]]) -> Tuple[str, str]:
        """
        Extract author name and URL from API data or canonical URL.

        Args:
            canonical_url: Canonical URL pointing to original Dev.to post
            api_data: Optional original Dev.to API response data

        Returns:
            Tuple of (author_name, author_url)
            Example: ("Alice", "https://dev.to/alice")

        """
        # Fallback: API data → URL parsing → defaults
        if api_data and "user" in api_data:
            user_data = api_data["user"]
            author_name = user_data.get("name", user_data.get("username", "Dev.to Author"))
            username = user_data.get("username")
            if username:
                return author_name, f"https://dev.to/{username}"

        if canonical_url:
            try:
                url_parts = canonical_url.split("/")
                if len(url_parts) >= 4 and "dev.to" in canonical_url:
                    username = url_parts[3]
                    return username, f"https://dev.to/{username}"
            except Exception:
                logger.debug("Failed to extract username from canonical URL")

        return "Dev.to Author", canonical_url

    def _extract_dates(self, post: Any, api_data: Optional[Dict[str, Any]]) -> Tuple[str, str]:
        published_date = ""
        if api_data:
            published_date = api_data.get("published_at", "")
        if not published_date:
            published_date = getattr(post, "date", "")

        published_date = self._ensure_iso_format(published_date)
        modified_date = published_date
        if api_data and api_data.get("edited_at"):
            modified_date = self._ensure_iso_format(api_data["edited_at"])

        return published_date, modified_date

    def _ensure_iso_format(self, date_str: Any) -> str:
        if not isinstance(date_str, str) or not date_str:
            return ""
        if "T" in date_str and not date_str.endswith("Z") and "+" not in date_str:
            return f"{date_str}Z"
        return date_str

    def _extract_image(self, post: Any, api_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        image_url = ""
        if api_data:
            image_url = api_data.get("social_image") or api_data.get("cover_image", "")
        if not image_url:
            image_url = getattr(post, "cover_image", "")

        if image_url:
            return {JSON_LD_TYPE: "ImageObject", "url": image_url, "width": 1000, "height": 500}
        return None

    def _extract_tags(self, post: Any, api_data: Optional[Dict[str, Any]]) -> list:
        tags = []
        if api_data:
            tags = api_data.get("tags", [])
        if not tags:
            tags = getattr(post, "tags", [])
        return tags if isinstance(tags, list) else []

    def _calculate_word_count(self, content_html: str) -> int:
        """
        Calculate word count from HTML content by stripping tags.

        Args:
            content_html: HTML content string to analyze

        Returns:
            Integer word count
            Example: "<p>Hello world</p>" returns 2

        """
        if not content_html:
            return 0
        text_content = re.sub(r"<[^>]+>", "", content_html)
        return len(text_content.split())

    def _extract_content_metrics(self, post: Any, api_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not post:
            return {}

        metrics: Dict[str, Any] = {}

        if api_data and "reading_time_minutes" in api_data:
            reading_time = api_data["reading_time_minutes"]
            if reading_time and reading_time > 0:
                metrics["timeRequired"] = f"PT{reading_time}M"

        word_count = self._calculate_word_count(getattr(post, "content_html", ""))
        if word_count > 0:
            metrics["wordCount"] = word_count

        if api_data and "language" in api_data:
            metrics["inLanguage"] = api_data["language"]

        return metrics

    def _create_interaction_counter(self, interaction_type: str, count: int) -> Dict[str, Any]:
        """
        Create a Schema.org InteractionCounter object.

        Args:
            interaction_type: Schema.org interaction type URL (e.g., "https://schema.org/LikeAction")
            count: Number of interactions

        Returns:
            Dictionary containing InteractionCounter schema
            Example: {"@type": "InteractionCounter", "interactionType": "...", "userInteractionCount": 7}

        """
        return {
            JSON_LD_TYPE: "InteractionCounter",
            "interactionType": interaction_type,
            "userInteractionCount": count,
        }

    def _collect_interaction_stats(self, api_data: Optional[Dict[str, Any]]) -> Dict[str, int]:
        """
        Collect interaction statistics from API data.

        Args:
            api_data: Optional original Dev.to API response data

        Returns:
            Dictionary mapping stat keys to integer counts
            Example: {"commentCount": 3, "interactionCount": 5, "pageViews": 100}

        Note:
            Uses strict isinstance(count, int) validation to ensure only valid
            integer counts are included. Filters out None values and negative counts.

        """
        if not api_data:
            return {}

        stats: Dict[str, int] = {}

        comments_count = api_data.get("comments_count")
        if isinstance(comments_count, int) and comments_count >= 0:
            stats["commentCount"] = comments_count

        reactions_count = api_data.get("public_reactions_count")
        if isinstance(reactions_count, int) and reactions_count >= 0:
            stats["interactionCount"] = reactions_count

        page_views = api_data.get("page_views_count")
        if isinstance(page_views, int) and page_views >= 0:
            stats["pageViews"] = page_views

        return stats

    def _extract_engagement_metrics(self, api_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract engagement metrics from API data.

        Args:
            api_data: Optional original Dev.to API response data (defaults to None)

        Returns:
            Dictionary with engagement metric fields including interactionStatistic
            and additionalProperty arrays when applicable
            Example: {"interactionStatistic": [...], "additionalProperty": [...]}

        Note:
            The api_data parameter defaults to None, allowing this method to be called
            without arguments when no API data is available.

        """
        interaction_stats = self._collect_interaction_stats(api_data)
        if not interaction_stats:
            return {}

        result: Dict[str, Any] = {}
        interaction_statistic = [
            self._create_interaction_counter(interaction_type, interaction_stats[key])
            for key, interaction_type in INTERACTION_TYPE_MAPPING.items()
            if key in interaction_stats
        ]

        if interaction_statistic:
            result["interactionStatistic"] = interaction_statistic

        if "pageViews" in interaction_stats:
            result["additionalProperty"] = [
                {JSON_LD_TYPE: "PropertyValue", "name": "pageViews", "value": interaction_stats["pageViews"]}
            ]

        return result

    def generate_article_schema(
        self, post: Any, canonical_url: str, api_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        author_name, author_url = self._extract_author_info(canonical_url, api_data)
        published_date, modified_date = self._extract_dates(post, api_data)

        schema = {
            JSON_LD_CONTEXT: SCHEMA_ORG_BASE,
            JSON_LD_TYPE: "Article",
            "headline": getattr(post, "title", "Untitled"),
            "author": {JSON_LD_TYPE: "Person", "name": author_name, "url": author_url},
            "publisher": {JSON_LD_TYPE: "Organization", "name": self.site_name, "url": self.site_url or canonical_url},
            "mainEntityOfPage": {JSON_LD_TYPE: "WebPage", "@id": canonical_url},
            "url": canonical_url,
        }

        if published_date:
            schema["datePublished"] = published_date
            schema["dateModified"] = modified_date

        description = getattr(post, "description", "")
        if description:
            schema["description"] = description

        image = self._extract_image(post, api_data)
        if image:
            schema["image"] = image

        tags = self._extract_tags(post, api_data)
        if tags:
            schema["keywords"] = tags

        content_metrics = self._extract_content_metrics(post, api_data)
        schema.update(content_metrics)

        engagement_metrics = self._extract_engagement_metrics(api_data)
        schema.update(engagement_metrics)

        if validate_json_ld_schema(schema):
            return schema

        logger.warning("Generated article schema failed validation")
        return {}

    def generate_website_schema(self, site_info: Dict[str, Any]) -> Dict[str, Any]:
        schema = {
            JSON_LD_CONTEXT: SCHEMA_ORG_BASE,
            JSON_LD_TYPE: "WebSite",
            "@id": site_info.get("url", self.site_url),
            "name": site_info.get("name", self.site_name),
            "url": site_info.get("url", self.site_url),
        }

        description = site_info.get("description")
        if description:
            schema["description"] = description

        if self.site_url:
            schema["potentialAction"] = {
                JSON_LD_TYPE: "SearchAction",
                "target": {JSON_LD_TYPE: "EntryPoint", "urlTemplate": f"{self.site_url}/?q={{search_term_string}}"},
                "query-input": "required name=search_term_string",
            }

        if validate_json_ld_schema(schema):
            return schema

        logger.warning("Generated website schema failed validation")
        return {}

    def generate_breadcrumb_schema(self, post: Any) -> Dict[str, Any]:
        breadcrumbs = [
            {JSON_LD_TYPE: "ListItem", "position": 1, "name": "Home", "item": self.site_url or "/"},
            {
                JSON_LD_TYPE: "ListItem",
                "position": 2,
                "name": "Posts",
                "item": f"{self.site_url}/posts" if self.site_url else "/posts",
            },
        ]

        post_title = getattr(post, "title", "Post")
        post_slug = getattr(post, "slug", "post")
        breadcrumbs.append(
            {
                JSON_LD_TYPE: "ListItem",
                "position": 3,
                "name": post_title,
                "item": f"{self.site_url}/posts/{post_slug}.html" if self.site_url else f"/posts/{post_slug}.html",
            }
        )

        schema = {JSON_LD_CONTEXT: SCHEMA_ORG_BASE, JSON_LD_TYPE: "BreadcrumbList", "itemListElement": breadcrumbs}

        if validate_json_ld_schema(schema):
            return schema

        logger.warning("Generated breadcrumb schema failed validation")
        return {}
