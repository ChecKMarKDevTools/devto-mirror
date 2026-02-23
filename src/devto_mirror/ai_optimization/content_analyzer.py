"""
Content Analysis Module for Dev.to Mirror

This module provides content analysis functionality for Dev.to posts,
including metrics extraction, language detection, and content type classification.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

# Configure logging for content analysis
logger = logging.getLogger(__name__)

_LANG_PATTERN_CLASS = "class "


class DevToContentAnalyzer:
    """
    Content analyzer for Dev.to posts.

    Extracts metrics, detects programming languages, and determines content types
    from Dev.to posts, prioritizing API data when available.
    """

    CONTENT_TYPE_MATCHERS = [
        (
            "tutorial",
            ["tutorial", "howto", "guide", "walkthrough", "stepbystep", "beginners"],
            ["how to", "tutorial", "guide", "walkthrough", "step by step"],
        ),
        (
            "discussion",
            ["discuss", "discussion", "watercooler", "community", "opinion", "thoughts"],
            ["thoughts on", "opinion", "discussion", "what do you think"],
        ),
        (
            "career",
            ["career", "job", "interview", "workplace", "professional"],
            ["career", "job", "interview", "workplace"],
        ),
        (
            "writing",
            ["writing", "writers", "blogging", "content"],
            ["writing", "blog", "content creation"],
        ),
        (
            "technology",
            ["technology", "tooling", "tools", "vscode", "webdev"],
            ["technology", "tools", "tech"],
        ),
        (
            "ai",
            ["ai", "githubcopilot", "chatgpt", "machinelearning", "ml"],
            ["ai", "artificial intelligence", "copilot", "chatgpt"],
        ),
        (
            "productivity",
            ["productivity", "workflow", "automation", "efficiency"],
            ["productivity", "workflow", "automation"],
        ),
        (
            "challenge",
            ["devchallenge", "challenge", "contest", "hackathon"],
            ["challenge", "contest", "hackathon"],
        ),
        (
            "wellness",
            ["mentalhealth", "wellness", "burnout", "health"],
            ["mental health", "wellness", "burnout"],
        ),
    ]

    # (API field name, minimum acceptable value)
    METRIC_CONFIG = [
        ("reading_time_minutes", 1),
        ("public_reactions_count", 0),
        ("comments_count", 0),
        ("word_count", 1),
        ("page_views_count", 0),
    ]

    def __init__(self):
        """Initialize content analyzer with logging configuration."""
        self.logger = logging.getLogger(__name__ + ".ContentAnalyzer")

    def analyze_post_content(self, post: Any, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze post content and extract semantic information.

        Args:
            post: Post object containing content
            api_data: Original Dev.to API response data

        Returns:
            Dictionary containing content analysis results with data source flags
        """
        analysis_result = {
            "metrics": {},
            "content_type": "",
            "code_languages": [],
            "data_source_flags": {},
            "analysis_timestamp": "",
        }

        try:
            # Extract metrics (API-first approach)
            api_metrics = self.extract_api_metrics(api_data)
            fallback_metrics = {}

            # Calculate fallback metrics if needed
            content_html = getattr(post, "content_html", "")
            if content_html and (not api_metrics or len(api_metrics) == 0):
                self.logger.info("Using fallback content analysis - API data not available")
                fallback_metrics = self.calculate_fallback_metrics(content_html)
            elif not api_metrics:
                self.logger.info("Using fallback content analysis - API metrics empty")
                fallback_metrics = self.calculate_fallback_metrics(content_html)

            # Combine metrics with data source tracking
            analysis_result["metrics"] = {**fallback_metrics, **api_metrics}

            # Track data sources
            analysis_result["data_source_flags"] = {
                "reading_time_source": "api" if "reading_time_minutes" in api_metrics else "calculated",
                "word_count_source": "api" if "word_count" in api_metrics else "calculated",
                "reactions_source": "api" if "public_reactions_count" in api_metrics else "unavailable",
                "api_data_available": bool(api_data and len(api_data) > 0),
            }

            # Determine content type
            analysis_result["content_type"] = self._determine_content_type(post, api_data)

            # Extract programming languages from code blocks and tags
            analysis_result["code_languages"] = self.extract_code_languages(content_html, api_data)

            # Add timestamp
            analysis_result["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()

            self.logger.debug(f"Content analysis completed for post: {getattr(post, 'slug', 'unknown')}")

        except Exception as e:
            self.logger.error(f"Content analysis failed: {e}")
            # Return minimal analysis result on error
            analysis_result["metrics"] = self.calculate_fallback_metrics(getattr(post, "content_html", ""))
            analysis_result["data_source_flags"] = {"error": str(e)}

        return analysis_result

    def _validate_numeric_metric(self, value: Any, min_value: int = 0) -> int | None:
        """
        Validate and convert a numeric metric value.

        Args:
            value: The value to validate (int or float)
            min_value: Minimum acceptable value (inclusive)

        Returns:
            Validated integer value or None if invalid

        Note:
            Float values are truncated toward zero (e.g., 5.7 becomes 5, -5.7 becomes -5).
            Boolean values are rejected even though bool is a subclass of int.
        """
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        int_value = int(value)
        return int_value if int_value >= min_value else None

    def extract_api_metrics(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metrics directly from Dev.to API data when available.

        Args:
            api_data: Original Dev.to API response

        Returns:
            Dictionary of metrics extracted from API (reading_time, reactions, etc.)
        """
        metrics = {}

        if not api_data or not isinstance(api_data, dict):
            self.logger.debug("No API data available for metric extraction")
            return metrics

        try:
            for metric_key, min_value in self.METRIC_CONFIG:
                raw_value = api_data.get(metric_key)
                if raw_value is None:
                    self.logger.debug(f"Metric {metric_key} not in API data")
                    continue
                validated_value = self._validate_numeric_metric(raw_value, min_value)
                if validated_value is not None:
                    metrics[metric_key] = validated_value
                    self.logger.debug(f"Extracted {metric_key}: {validated_value}")
                else:
                    self.logger.debug(f"Metric {metric_key}={raw_value} rejected (min={min_value})")

            total_metrics = len(self.METRIC_CONFIG)
            if metrics:
                self.logger.info(f"Extracted {len(metrics)} of {total_metrics} metrics from API data")
            else:
                self.logger.debug("No usable metrics found in API data")

        except Exception as e:
            self.logger.warning(f"Error extracting API metrics: {e}")

        return metrics

    def calculate_fallback_metrics(self, content: str) -> Dict[str, Any]:
        """
        Calculate basic metrics when API data is unavailable.

        Args:
            content: HTML content string to analyze

        Returns:
            Dictionary of calculated metrics (word_count, estimated_reading_time)
        """
        metrics = {}

        if not content or not isinstance(content, str):
            self.logger.debug("No content available for fallback metric calculation")
            return metrics

        try:
            # Remove HTML tags to get plain text
            text_content = re.sub(r"<[^>]+>", "", content)

            # Remove extra whitespace
            text_content = " ".join(text_content.split())

            # Calculate word count
            if text_content:
                words = text_content.split()
                word_count = len(words)
                metrics["word_count"] = word_count

                # Estimate reading time (average 200 words per minute)
                if word_count > 0:
                    reading_time_minutes = max(1, round(word_count / 200))
                    metrics["reading_time_minutes"] = reading_time_minutes

                self.logger.debug(
                    f"Calculated fallback metrics: {word_count} words, {reading_time_minutes} min reading time"
                )

            # Calculate content length metrics
            metrics["content_length_chars"] = len(content)
            metrics["text_length_chars"] = len(text_content)

            # Count code blocks (basic estimation)
            code_blocks = re.findall(r"<pre[^>]*>.*?</pre>", content, re.DOTALL | re.IGNORECASE)
            code_blocks += re.findall(r"<code[^>]*>.*?</code>", content, re.DOTALL | re.IGNORECASE)
            metrics["code_blocks_count"] = len(code_blocks)

            # Count images
            images = re.findall(r"<img[^>]*>", content, re.IGNORECASE)
            metrics["images_count"] = len(images)

            # Count links
            links = re.findall(r"<a[^>]*href[^>]*>", content, re.IGNORECASE)
            metrics["links_count"] = len(links)

        except Exception as e:
            self.logger.warning(f"Error calculating fallback metrics: {e}")
            # Provide minimal fallback
            metrics = {
                "word_count": 0,
                "reading_time_minutes": 1,
                "content_length_chars": len(content) if content else 0,
            }

        return metrics

    def extract_code_languages(self, content: str, api_data: Dict[str, Any] = None) -> List[str]:
        """
        Identify programming languages from code blocks in content and Dev.to tags.

        Args:
            content: HTML content containing code blocks
            api_data: Optional Dev.to API data containing tag_list

        Returns:
            List of detected programming language identifiers
        """
        languages = set()

        if api_data:
            tag_languages = self._extract_languages_from_tags(api_data)
            languages.update(tag_languages)

        if not content or not isinstance(content, str):
            return sorted(languages)

        try:
            languages.update(self._extract_languages_from_attributes(content))
            languages.update(self._extract_languages_from_fenced_blocks(content))

            code_content = self._extract_code_block_content(content)
            if code_content:
                detected_langs = self._detect_languages_by_keywords(code_content)
                languages.update(detected_langs)

            result = self._normalize_and_sort_languages(languages)

            if result:
                self.logger.debug(f"Detected programming languages: {result}")

            return result

        except Exception as e:
            self.logger.warning(f"Error extracting code languages: {e}")
            return []

    def _extract_languages_from_attributes(self, content: str) -> set:
        """Extract programming languages from HTML class and data attributes."""
        languages = set()
        lang_class_patterns = [
            r'class=["\'][^"\']*(?:language|lang)-([a-zA-Z0-9+#-]+)',
            r'data-lang=["\']([a-zA-Z0-9+#-]+)["\']',
            r'data-language=["\']([a-zA-Z0-9+#-]+)["\']',
        ]

        for pattern in lang_class_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                lang = match.lower().strip()
                if lang and len(lang) <= 20:
                    languages.add(lang)

        return languages

    def _extract_languages_from_fenced_blocks(self, content: str) -> set:
        """Extract programming languages from fenced code blocks (```language)."""
        languages = set()
        fenced_blocks = re.findall(r"```([a-zA-Z0-9+#-]+)", content)
        for lang in fenced_blocks:
            lang = lang.lower().strip()
            if lang and len(lang) <= 20:
                languages.add(lang)

        return languages

    def _normalize_and_sort_languages(self, languages: set) -> List[str]:
        """Normalize language names and return sorted list."""
        normalized_languages = []
        for lang in languages:
            normalized = self._normalize_language_name(lang)
            if normalized:
                normalized_languages.append(normalized)

        return sorted(list(set(normalized_languages)))

    def _extract_code_block_content(self, content: str) -> str:
        """Extract text content from code blocks for language detection."""
        code_blocks = []

        # Extract content from <pre> and <code> tags
        pre_blocks = re.findall(r"<pre[^>]*>(.*?)</pre>", content, re.DOTALL | re.IGNORECASE)
        code_blocks.extend(pre_blocks)

        code_tags = re.findall(r"<code[^>]*>(.*?)</code>", content, re.DOTALL | re.IGNORECASE)
        code_blocks.extend(code_tags)

        # Clean HTML tags from extracted content
        combined_code = " ".join(code_blocks)
        clean_code = re.sub(r"<[^>]+>", "", combined_code)

        return clean_code

    def _detect_languages_by_keywords(self, code_content: str) -> List[str]:
        """Detect programming languages based on common keywords and patterns."""
        if not code_content or len(code_content.strip()) < 10:
            return []

        detected = []
        code_lower = code_content.lower()

        # Language detection patterns (basic heuristics)
        language_patterns = {
            "python": ["def ", "import ", "from ", "print(", "__init__", "elif ", "self."],
            "javascript": ["function ", "var ", "let ", "const ", "console.log", "=>", "document."],
            "typescript": ["interface ", "type ", ": string", ": number", ": boolean"],
            "java": ["public class", "private ", "public static void main", "System.out"],
            "csharp": ["using System", "public class", "Console.WriteLine", "namespace "],
            "cpp": ["#include", "std::", "cout <<", "int main()", "using namespace"],
            "c": ["#include", "printf(", "int main()", "malloc(", "free("],
            "go": ["package ", "func ", "import (", "fmt.Print", "go "],
            "rust": ["fn ", "let mut", "println!", "use std::", "impl "],
            "php": ["<?php", "echo ", "$_GET", "$_POST", "function "],
            "ruby": ["def ", "end", "puts ", "require ", _LANG_PATTERN_CLASS],
            "swift": ["func ", "var ", "let ", "import Foundation", "print("],
            "kotlin": ["fun ", "val ", "var ", "println(", _LANG_PATTERN_CLASS],
            "scala": ["def ", "val ", "var ", "object ", _LANG_PATTERN_CLASS],
            "sql": ["SELECT ", "FROM ", "WHERE ", "INSERT INTO", "UPDATE ", "DELETE "],
            "html": ["<html", "<div", "<span", "<body", "<!DOCTYPE"],
            "css": ["{", "}", "margin:", "padding:", "color:", "background:"],
            "bash": ["#!/bin/bash", "echo ", "export ", "if [", "fi"],
            "yaml": ["---", "- name:", "version:", "dependencies:"],
            "json": ['{"', '"}', '":', "[{", "}]"],
            "xml": ["<?xml", "</", "/>"],
        }

        for language, patterns in language_patterns.items():
            matches = sum(1 for pattern in patterns if pattern in code_lower)
            # If we find multiple patterns for a language, it's likely that language
            if matches >= 2 or (matches == 1 and len(patterns) <= 3):  # For languages with fewer patterns
                detected.append(language)

        return detected

    def _normalize_language_name(self, lang: str) -> str:
        """Normalize language names to standard identifiers."""
        if not lang:
            return ""

        lang = lang.lower().strip()

        # Language name mappings
        language_mappings = {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "rb": "ruby",
            "cs": "csharp",
            "c++": "cpp",
            "c#": "csharp",
            "golang": "go",
            "yml": "yaml",
            "sh": "bash",
            "shell": "bash",
            "htm": "html",
        }

        # Apply mappings
        normalized = language_mappings.get(lang, lang)

        # Validate that it's a reasonable language name
        if len(normalized) > 20 or not normalized.replace("+", "").replace("#", "").replace("-", "").isalnum():
            return ""

        return normalized

    def _get_language_for_tag(self, tag_lower: str, programming_language_tags: set, framework_to_language: dict) -> str:
        """Resolve a tag to a normalized language name, or return empty string."""
        if tag_lower in programming_language_tags:
            return self._normalize_language_name(tag_lower)
        if tag_lower in framework_to_language:
            return self._normalize_language_name(framework_to_language[tag_lower])
        return ""

    def _extract_languages_from_tags(self, api_data: Dict[str, Any]) -> List[str]:
        """
        Extract programming languages from Dev.to tag_list.

        Args:
            api_data: Dev.to API response data

        Returns:
            List of programming languages found in tags
        """
        languages = set()

        if not api_data or not isinstance(api_data, dict):
            return []

        # Get tags from API data
        tags = api_data.get("tag_list", [])
        if not tags and "tags" in api_data:
            tags = api_data.get("tags", [])

        if not isinstance(tags, list):
            return []

        # Common programming language tags used on Dev.to
        programming_language_tags = {
            "javascript",
            "js",
            "typescript",
            "ts",
            "python",
            "py",
            "java",
            "csharp",
            "c#",
            "cs",
            "cpp",
            "c++",
            "c",
            "go",
            "golang",
            "rust",
            "php",
            "ruby",
            "rb",
            "swift",
            "kotlin",
            "scala",
            "dart",
            "r",
            "matlab",
            "perl",
            "lua",
            "haskell",
            "clojure",
            "elixir",
            "erlang",
            "fsharp",
            "f#",
            "ocaml",
            "nim",
            "crystal",
            "zig",
            "v",
            "julia",
            "bash",
            "shell",
            "powershell",
            "sql",
            "html",
            "css",
            "scss",
            "sass",
            "less",
            "xml",
            "yaml",
            "yml",
            "json",
            "toml",
            "ini",
            "dockerfile",
            "makefile",
            "assembly",
            "asm",
            "vhdl",
            "verilog",
            "solidity",
            "move",
            "cairo",
        }

        # Framework/library tags that imply languages
        framework_to_language = {
            "react": "javascript",
            "vue": "javascript",
            "angular": "javascript",
            "svelte": "javascript",
            "nodejs": "javascript",
            "node": "javascript",
            "express": "javascript",
            "nextjs": "javascript",
            "nuxtjs": "javascript",
            "gatsby": "javascript",
            "electron": "javascript",
            "django": "python",
            "flask": "python",
            "fastapi": "python",
            "pandas": "python",
            "numpy": "python",
            "tensorflow": "python",
            "pytorch": "python",
            "scikit": "python",
            "spring": "java",
            "springboot": "java",
            "hibernate": "java",
            "maven": "java",
            "gradle": "java",
            "dotnet": "csharp",
            "aspnet": "csharp",
            "blazor": "csharp",
            "xamarin": "csharp",
            "rails": "ruby",
            "sinatra": "ruby",
            "jekyll": "ruby",
            "laravel": "php",
            "symfony": "php",
            "wordpress": "php",
            "drupal": "php",
            "gin": "go",
            "echo": "go",
            "fiber": "go",
            "beego": "go",
            "actix": "rust",
            "rocket": "rust",
            "warp": "rust",
            "tokio": "rust",
            "flutter": "dart",
            "android": "java",
            "ios": "swift",
            "swiftui": "swift",
            "bootstrap": "css",
            "tailwind": "css",
            "bulma": "css",
            "materialize": "css",
        }

        # Check each tag
        for tag in tags:
            if not isinstance(tag, str):
                continue
            lang = self._get_language_for_tag(tag.lower().strip(), programming_language_tags, framework_to_language)
            if lang:
                languages.add(lang)

        result = sorted(languages)
        if result:
            self.logger.debug(f"Extracted languages from tags: {result}")

        return result

    def _extract_tags(self, post: Any, api_data: Dict[str, Any]) -> List[str]:
        """
        Extract and normalize tags from API data or post object.

        Args:
            post: Post object to analyze
            api_data: Original Dev.to API response data

        Returns:
            List of lowercase tag strings
        """
        tags = []
        if api_data and "tags" in api_data:
            tags = api_data.get("tags", [])
        elif api_data and "tag_list" in api_data:
            tags = api_data.get("tag_list", [])

        if not tags:
            tags = getattr(post, "tags", [])

        if not isinstance(tags, list):
            return []

        return [tag.lower() for tag in tags if isinstance(tag, str)]

    def _matches_content_type(
        self, tags_lower: List[str], title: str, tag_keywords: List[str], title_keywords: List[str]
    ) -> bool:
        """
        Check if tags or title match content type keywords.

        Args:
            tags_lower: Lowercase tags from post
            title: Lowercase title from post
            tag_keywords: Keywords to search in tags
            title_keywords: Keywords to search in title

        Returns:
            True if any keyword matches
        """
        if any(tag in tags_lower for tag in tag_keywords):
            return True
        if any(word in title for word in title_keywords):
            return True
        return False

    def _determine_content_type(self, post: Any, api_data: Dict[str, Any]) -> str:
        """
        Determine the content type of the post based on tags and content.

        Args:
            post: Post object to analyze
            api_data: Original Dev.to API response data

        Returns:
            String indicating content type (tutorial, article, discussion, etc.)
        """
        tags_lower = self._extract_tags(post, api_data)
        title = getattr(post, "title", "").lower()

        for content_type, tag_keywords, title_keywords in self.CONTENT_TYPE_MATCHERS:
            if self._matches_content_type(tags_lower, title, tag_keywords, title_keywords):
                return content_type

        return "article"
