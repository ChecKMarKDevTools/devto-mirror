"""
Dev.to API client utilities.

Provides session management, retry logic, and article filtering
for interacting with the Dev.to API.
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


def create_devto_session() -> requests.Session:
    """
    Create a configured requests session for Dev.to API calls.

    Configures appropriate headers for the Dev.to V1 API including
    User-Agent and Accept headers. Automatically detects CI environments
    and uses GitHub Actions-specific User-Agent string.

    Environment Variables:
        CI: Set to "true" to indicate CI environment
        GITHUB_ACTIONS: Set to "true" to indicate GitHub Actions
        DEVTO_KEY: Optional API key for higher rate limits

    Returns:
        Configured requests.Session with appropriate headers
    """
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    if is_ci:
        print("🤖 Running in CI environment - using conservative timeouts and delays")

    session = requests.Session()
    headers = {
        "User-Agent": "DevTo-Mirror-Bot/1.0 (GitHub-Actions)" if is_ci else "DevTo-Mirror-Bot/1.0",
        "Accept": "application/vnd.forem.api-v1+json",
    }

    api_key = os.getenv("DEVTO_KEY")
    if api_key:
        headers["api-key"] = api_key

    session.headers.update(headers)
    return session


def fetch_page_with_retry(
    session: requests.Session,
    url: str,
    params: dict,
    page: int,
    max_retries: int = 3,
    timeout: int = 30,
) -> Optional[List[dict]]:
    """
    Fetch a page of articles with automatic retry on transient failures.

    Implements exponential backoff for ReadTimeout and ConnectionError only.
    Other RequestException types (e.g., HTTPError for 4xx/5xx) fail immediately.
    Returns None on persistent failures to allow graceful degradation.

    Args:
        session: Configured requests session
        url: API endpoint URL
        params: Query parameters for the request
        page: Page number (used for logging)
        max_retries: Maximum retry attempts (default: 3)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        List of article dictionaries on success, None on failure
    """
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()

        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                print(f"  ⚠️  Timeout on page {page}, attempt {attempt + 1}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"  ❌ Failed to fetch page {page} after {max_retries} attempts: {e}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Request error for page {page}: {e}")
            return None

    return None


def _parse_api_timestamp(value: object) -> datetime | None:
    """Parse a Dev.to API timestamp string to a timezone-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def filter_new_articles(data: List[dict], last_run_iso: Optional[str]) -> List[dict]:
    """
    Filter articles to only include those published after last run.

    Args:
        data: List of article dictionaries from API
        last_run_iso: ISO 8601 timestamp with timezone offset (e.g., "2024-01-15T10:30:00+00:00").
                      The "Z" suffix is NOT supported; use "+00:00" for UTC.
                      Pass None to return all articles without filtering.

    Returns:
        Filtered list containing only articles newer than last_run_iso,
        or all articles if last_run_iso is None.

    Raises:
        ValueError: If last_run_iso is not a valid ISO 8601 format string.

    Note:
        Article timestamps from Dev.to API use "Z" suffix which is converted
        internally to "+00:00" for proper comparison. Articles with missing
        or malformed published_at fields are silently skipped.
    """
    if not last_run_iso:
        return data

    try:
        last_run_dt = datetime.fromisoformat(last_run_iso)
    except ValueError as e:
        logger.error(f"Invalid ISO format for last_run_iso: {last_run_iso}")
        raise ValueError(f"last_run_iso must be valid ISO 8601 format: {e}") from e

    # Normalize naive datetimes to UTC for safe comparison.
    if last_run_dt.tzinfo is None:
        last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)

    def _activity_timestamp(article: dict) -> datetime | None:
        # Dev.to commonly provides: created_at, published_at, edited_at.
        # We treat a post as "new since last run" if it was *published or edited* since last run.
        candidates = [
            article.get("edited_at"),
            article.get("updated_at"),
            article.get("published_at"),
        ]
        dts = [dt for dt in (_parse_api_timestamp(v) for v in candidates) if dt is not None]
        return max(dts) if dts else None

    result: list[dict] = []
    for article in data:
        activity_dt = _activity_timestamp(article)
        if activity_dt is None:
            logger.debug(f"Skipping article without parseable activity timestamp: {article.get('id', 'unknown')}")
            continue
        if activity_dt > last_run_dt:
            result.append(article)

    return result
