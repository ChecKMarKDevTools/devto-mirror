"""
AI-Optimized Sitemap Generator for Dev.to Mirror

This module provides AI-optimized sitemap generation that extends the existing
sitemap functionality with AI-specific metadata while maintaining backward
compatibility with the current sitemap.xml format.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape  # nosec B406

from .utils import determine_content_type as classify_content_type

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'

logger = logging.getLogger(__name__)


class DevToAISitemapGenerator:
    """
    Concrete implementation of AI-optimized sitemap generation for Dev.to mirror sites.

    Extends existing sitemap functionality with AI-specific metadata while maintaining
    backward compatibility with current sitemap.xml format.
    """

    def __init__(self, site_url: str = "", site_name: str = "ChecKMarK Dev.to Mirror"):
        """
        Initialize AI sitemap generator with site information.

        Args:
            site_url: Base URL of the mirror site
            site_name: Name of the mirror site for metadata
        """
        self.site_url = site_url.rstrip("/")
        self.site_name = site_name

    def generate_main_sitemap(self, posts: List[Any], comments: List[Dict[str, Any]]) -> str:
        """
        Generate main sitemap.xml with AI optimization enhancements.

        Args:
            posts: List of Post objects
            comments: List of comment page dictionaries

        Returns:
            XML string for main sitemap with enhanced metadata
        """
        try:
            sitemap_entries = []

            # Add home page entry with high priority
            home_url = self.site_url or "/"
            sitemap_entries.append(
                self._create_url_entry(
                    loc=home_url, lastmod=self._get_latest_post_date(posts), changefreq="daily", priority="1.0"
                )
            )

            # Add post entries with AI-enhanced metadata
            for post in posts:
                entry = self._create_post_url_entry(post)
                if entry:
                    sitemap_entries.append(entry)

            # Add comment entries
            for comment in comments:
                entry = self._create_comment_url_entry(comment)
                if entry:
                    sitemap_entries.append(entry)

            # Generate XML sitemap
            xml_content = self._generate_sitemap_xml(sitemap_entries)
            return xml_content

        except Exception as e:
            logger.error(f"Failed to generate main sitemap: {e}")
            # Fallback to basic sitemap format
            return self._generate_basic_sitemap(posts, comments)

    def generate_content_sitemap(self, posts: List[Any]) -> str:
        """
        Generate content-type specific sitemap for AI crawlers.

        Args:
            posts: List of Post objects to categorize

        Returns:
            XML string for content-specific sitemap
        """
        try:
            # Categorize posts by content type
            categorized_posts = self._categorize_posts_by_type(posts)

            sitemap_entries = []

            # Add entries for each content category
            for content_type, type_posts in categorized_posts.items():
                if not type_posts:
                    continue

                # Add category index entry
                category_url = (
                    f"{self.site_url}/content/{content_type}" if self.site_url else f"/content/{content_type}"
                )
                sitemap_entries.append(
                    self._create_url_entry(
                        loc=category_url,
                        lastmod=self._get_latest_post_date(type_posts),
                        changefreq="weekly",
                        priority="0.8",
                    )
                )

                # Add individual posts in this category
                for post in type_posts:
                    entry = self._create_post_url_entry(post, content_type=content_type)
                    if entry:
                        sitemap_entries.append(entry)

            return self._generate_sitemap_xml(sitemap_entries)

        except Exception as e:
            logger.error(f"Failed to generate content sitemap: {e}")
            return ""

    def generate_discovery_feed(self, posts: List[Any]) -> str:
        """
        Generate AI crawler discovery feed with structured metadata.

        Args:
            posts: List of Post objects for discovery feed

        Returns:
            XML string optimized for AI crawler discovery
        """
        try:
            # Create RSS-style feed optimized for AI discovery
            feed_entries = []

            # Sort posts by date (newest first)
            sorted_posts = sorted(posts, key=lambda p: self._get_post_date(p) or datetime.min, reverse=True)

            # Take the most recent posts for the discovery feed
            recent_posts = sorted_posts[:50]  # Limit to 50 most recent posts

            for post in recent_posts:
                entry = self._create_discovery_entry(post)
                if entry:
                    feed_entries.append(entry)

            return self._generate_discovery_xml(feed_entries)

        except Exception as e:
            logger.error(f"Failed to generate discovery feed: {e}")
            return ""

    def _create_url_entry(
        self, loc: str, lastmod: Optional[str] = None, changefreq: Optional[str] = None, priority: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a sitemap URL entry with optional metadata.

        Args:
            loc: URL location
            lastmod: Last modification date (ISO format)
            changefreq: Change frequency hint
            priority: Priority hint (0.0-1.0)

        Returns:
            Dictionary containing URL entry data
        """
        entry = {"loc": escape(loc)}

        if lastmod:
            entry["lastmod"] = lastmod
        if changefreq:
            entry["changefreq"] = changefreq
        if priority:
            entry["priority"] = priority

        return entry

    def _create_post_url_entry(self, post: Any, content_type: str = None) -> Dict[str, Any]:
        """
        Create a sitemap URL entry for a blog post with AI-enhanced metadata.

        Args:
            post: Post object
            content_type: Optional content type classification

        Returns:
            Dictionary containing post URL entry data
        """
        try:
            # Prefer canonical Dev.to link if available
            canonical_url = getattr(post, "link", "")
            if canonical_url:
                loc = canonical_url
            else:
                slug = getattr(post, "slug", "")
                if not slug:
                    return None
                loc = f"{self.site_url}/posts/{slug}.html" if self.site_url else f"/posts/{slug}.html"

            # Get post modification date
            post_date = self._get_post_date(post)
            lastmod = post_date.isoformat() if post_date else None

            # Determine change frequency based on post age and type
            changefreq = self._determine_post_changefreq(post)

            # Determine priority based on content type and engagement
            priority = self._determine_post_priority(post, content_type)

            return self._create_url_entry(loc, lastmod, changefreq, priority)

        except Exception as e:
            logger.debug(f"Failed to create URL entry for post: {e}")
            return None

    def _create_comment_url_entry(self, comment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a sitemap URL entry for a comment page.

        Args:
            comment: Comment dictionary with URL information

        Returns:
            Dictionary containing comment URL entry data
        """
        try:
            # Use provided URL or construct local URL
            loc = comment.get("url") or comment.get("local", "")
            if not loc:
                return None

            if not loc.startswith("http") and self.site_url:
                loc = f"{self.site_url}/{loc.lstrip('/')}"

            return self._create_url_entry(loc=loc, changefreq="monthly", priority="0.3")

        except Exception as e:
            logger.debug(f"Failed to create URL entry for comment: {e}")
            return None

    def _create_discovery_entry(self, post: Any) -> Dict[str, Any]:
        """
        Create a discovery feed entry for a post with rich metadata.

        Args:
            post: Post object

        Returns:
            Dictionary containing discovery entry data
        """
        try:
            title = getattr(post, "title", "Untitled")
            description = getattr(post, "description", "")
            canonical_url = getattr(post, "link", "")
            post_date = self._get_post_date(post)
            tags = getattr(post, "tags", [])

            # Get API data if available for additional metadata
            api_data = getattr(post, "api_data", {})
            reading_time = api_data.get("reading_time_minutes", 0) if api_data else 0
            reactions_count = api_data.get("public_reactions_count", 0) if api_data else 0

            entry = {
                "title": escape(title),
                "link": escape(canonical_url) if canonical_url else "",
                "description": escape(description) if description else "",
                "pubDate": post_date.strftime("%a, %d %b %Y %H:%M:%S %z") if post_date else "",
                "tags": tags if isinstance(tags, list) else [],
                "readingTime": reading_time,
                "reactions": reactions_count,
            }

            return entry

        except Exception as e:
            logger.debug(f"Failed to create discovery entry for post: {e}")
            return None

    def _categorize_posts_by_type(self, posts: List[Any]) -> Dict[str, List[Any]]:
        """
        Categorize posts by content type based on tags and content analysis.

        Args:
            posts: List of Post objects

        Returns:
            Dictionary mapping content types to lists of posts
        """
        categories = {
            "tutorial": [],
            "discussion": [],
            "career": [],
            "ai": [],
            "technology": [],
            "productivity": [],
            "article": [],
        }

        for post in posts:
            content_type = self._determine_content_type(post)
            if content_type in categories:
                categories[content_type].append(post)
            else:
                categories["article"].append(post)

        return categories

    def _determine_content_type(self, post: Any) -> str:
        """
        Determine the content type of a post based on tags and content.

        Args:
            post: Post object to analyze

        Returns:
            String indicating content type
        """
        tags = getattr(post, "tags", [])
        if not tags:
            api_data = getattr(post, "api_data", {})
            if api_data:
                tags = api_data.get("tags", [])

        return classify_content_type(tags)

    def _determine_post_changefreq(self, post: Any) -> str:
        """
        Determine change frequency for a post based on age.

        Args:
            post: Post object

        Returns:
            Change frequency string
        """
        post_date = self._get_post_date(post)
        if not post_date:
            return "monthly"

        # Calculate post age
        age_days = (datetime.now() - post_date.replace(tzinfo=None)).days

        # Newer posts change more frequently
        if age_days < 7:
            return "daily"
        elif age_days < 30:
            return "weekly"
        elif age_days < 90:
            return "monthly"
        else:
            return "yearly"

    def _determine_post_priority(self, post: Any, content_type: str = None) -> str:
        """
        Determine priority for a post based on content type and engagement.

        Args:
            post: Post object
            content_type: Optional content type classification

        Returns:
            Priority string (0.0-1.0)
        """
        base_priority = 0.5

        # Adjust priority based on content type
        if content_type == "tutorial":
            base_priority = 0.9
        elif content_type == "ai":
            base_priority = 0.8
        elif content_type == "technology":
            base_priority = 0.7
        elif content_type == "discussion":
            base_priority = 0.6

        # Adjust based on engagement metrics if available
        api_data = getattr(post, "api_data", {})
        if api_data:
            reactions = api_data.get("public_reactions_count", 0)
            if reactions > 50:
                base_priority = min(1.0, base_priority + 0.1)
            elif reactions > 20:
                base_priority = min(1.0, base_priority + 0.05)

        return f"{base_priority:.1f}"

    def _get_post_date(self, post: Any) -> Optional[datetime]:
        """
        Extract date from post object, handling various formats.

        Args:
            post: Post object

        Returns:
            datetime object or None if date cannot be parsed
        """
        # Try to get date from post object
        date_str = getattr(post, "date", "")

        # Try to get from API data if not available
        if not date_str:
            api_data = getattr(post, "api_data", {})
            if api_data:
                date_str = api_data.get("published_at", "")

        if not date_str:
            return None

        # Parse date string
        try:
            if isinstance(date_str, datetime):
                return date_str

            # Handle ISO format with Z
            if date_str.endswith("Z"):
                date_str = date_str.replace("Z", "+00:00")

            return datetime.fromisoformat(date_str)
        except Exception as e:
            logger.debug(f"Failed to parse date '{date_str}': {e}")
            return None

    def _get_latest_post_date(self, posts: List[Any]) -> str:
        """
        Get the latest modification date from a list of posts.

        Args:
            posts: List of Post objects

        Returns:
            ISO format date string of the latest post
        """
        latest_date = None

        for post in posts:
            post_date = self._get_post_date(post)
            if post_date and (not latest_date or post_date > latest_date):
                latest_date = post_date

        return latest_date.isoformat() if latest_date else datetime.now().isoformat()

    def _generate_sitemap_xml(self, entries: List[Dict[str, Any]]) -> str:
        """
        Generate XML sitemap from URL entries.

        Args:
            entries: List of URL entry dictionaries

        Returns:
            XML sitemap string
        """
        xml_lines = [
            XML_DECLARATION,
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        for entry in entries:
            xml_lines.append("  <url>")
            xml_lines.append(f"    <loc>{entry['loc']}</loc>")

            if entry.get("lastmod"):
                xml_lines.append(f"    <lastmod>{entry['lastmod']}</lastmod>")
            if entry.get("changefreq"):
                xml_lines.append(f"    <changefreq>{entry['changefreq']}</changefreq>")
            if entry.get("priority"):
                xml_lines.append(f"    <priority>{entry['priority']}</priority>")

            xml_lines.append("  </url>")

        xml_lines.append("</urlset>")
        return "\n".join(xml_lines)

    def _generate_discovery_xml(self, entries: List[Dict[str, Any]]) -> str:
        """
        Generate XML discovery feed from entry data.

        Args:
            entries: List of discovery entry dictionaries

        Returns:
            XML discovery feed string
        """
        xml_lines = [
            XML_DECLARATION,
            '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" ',
            'xmlns:ai="http://ai-optimization.dev/rss/1.0/">',
            "  <channel>",
            f"    <title>{escape(self.site_name)}</title>",
            f"    <link>{escape(self.site_url)}</link>",
            f"    <description>AI-optimized discovery feed for {escape(self.site_name)}</description>",
            "    <language>en-us</language>",
            f"    <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}</lastBuildDate>",
        ]

        for entry in entries:
            if not entry.get("title") or not entry.get("link"):
                continue

            xml_lines.append("    <item>")
            xml_lines.append(f"      <title>{entry['title']}</title>")
            xml_lines.append(f"      <link>{entry['link']}</link>")

            if entry.get("description"):
                xml_lines.append(f"      <description>{entry['description']}</description>")
            if entry.get("pubDate"):
                xml_lines.append(f"      <pubDate>{entry['pubDate']}</pubDate>")

            # Add AI-specific metadata
            if entry.get("readingTime"):
                xml_lines.append(f"      <ai:readingTime>{entry['readingTime']}</ai:readingTime>")
            if entry.get("reactions"):
                xml_lines.append(f"      <ai:reactions>{entry['reactions']}</ai:reactions>")

            # Add tags as categories
            for tag in entry.get("tags", []):
                xml_lines.append(f"      <category>{escape(str(tag))}</category>")

            xml_lines.append("    </item>")

        xml_lines.extend(["  </channel>", "</rss>"])

        return "\n".join(xml_lines)

    def _build_post_url(self, post: Any) -> str:
        """Return the best URL for a post: canonical first, then local slug-based."""
        canonical_url = getattr(post, "link", "")
        if canonical_url:
            return canonical_url
        slug = getattr(post, "slug", "")
        if slug:
            return f"{self.site_url}/posts/{slug}.html" if self.site_url else f"/posts/{slug}.html"
        return ""

    def _build_comment_url(self, comment: Dict[str, Any]) -> str:
        """Return the absolute URL for a comment entry."""
        url = comment.get("url") or comment.get("local", "")
        if url and not url.startswith("http") and self.site_url:
            return f"{self.site_url}/{url.lstrip('/')}"
        return url

    def _generate_basic_sitemap(self, posts: List[Any], comments: List[Dict[str, Any]]) -> str:
        """
        Generate basic sitemap as fallback when AI optimization fails.

        Args:
            posts: List of Post objects
            comments: List of comment dictionaries

        Returns:
            Basic XML sitemap string
        """
        xml_lines = [
            XML_DECLARATION,
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        # Add home page
        home_url = self.site_url or "/"
        xml_lines.append(f"  <url><loc>{escape(home_url)}</loc></url>")

        # Add posts
        for post in posts:
            url = self._build_post_url(post)
            if url:
                xml_lines.append(f"  <url><loc>{escape(url)}</loc></url>")

        # Add comments
        for comment in comments:
            url = self._build_comment_url(comment)
            if url:
                xml_lines.append(f"  <url><loc>{escape(url)}</loc></url>")

        xml_lines.append("</urlset>")
        return "\n".join(xml_lines)
