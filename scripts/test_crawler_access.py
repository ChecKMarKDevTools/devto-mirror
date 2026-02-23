#!/usr/bin/env python3

"""
Crawler accessibility testing script for Dev.to Mirror.

This script tests whether major search engine crawlers can access the site
by simulating different user agents and testing access to sample pages.
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import requests

# Major crawler user agents to test
CRAWLER_USER_AGENTS = {
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot)",
    "ClaudeBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; " + "ClaudeBot/1.0; +claudebot@anthropic.com)"
    ),
    "Claude-Web": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-Web/1.0; +https://claude.ai/)",
    "PerplexityBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; "
        "+https://perplexity.ai/bot)"
    ),
    "DuckDuckBot": "DuckDuckBot/1.0; (+http://duckduckgo.com/duckduckbot.html)",
    "Bytespider": (
        "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)"
    ),
    "CCBot": "Mozilla/5.0 (compatible; CCBot/2.0; https://commoncrawl.org/faq/)",
    "facebookexternalhit": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Twitterbot": "Twitterbot/1.0",
    "LinkedInBot": "LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)",
}

# Test pages to check (relative to base URL)
TEST_PAGES = [
    "",  # Index page
    "robots.txt",
    "sitemap.xml",
]


class CrawlerAccessTester:
    def __init__(self, base_url, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results = {}

    def test_crawler_access(self, crawler_name, user_agent, test_pages=None):
        """Test access for a specific crawler user agent."""
        if test_pages is None:
            test_pages = TEST_PAGES

        print(f"\nTesting {crawler_name}...")
        crawler_results = {
            "user_agent": user_agent,
            "pages": {},
            "summary": {"accessible": 0, "blocked": 0, "errors": 0},
        }

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        for page in test_pages:
            url = urljoin(self.base_url + "/", page)
            page_result = self._test_page_access(url, headers)
            crawler_results["pages"][page or "index"] = page_result

            # Update summary
            if page_result["accessible"]:
                crawler_results["summary"]["accessible"] += 1
            elif page_result["status_code"] in [403, 429, 503]:
                crawler_results["summary"]["blocked"] += 1
            else:
                crawler_results["summary"]["errors"] += 1

            # Be respectful - add delay between requests
            time.sleep(0.5)

        self.results[crawler_name] = crawler_results
        return crawler_results

    def _test_page_access(self, url, headers):
        """Test access to a specific page."""
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)

            result = {
                "url": url,
                "status_code": response.status_code,
                "accessible": response.status_code == 200,
                "response_time": response.elapsed.total_seconds(),
                "content_length": len(response.content) if response.content else 0,
                "content_type": response.headers.get("content-type", ""),
                "error": None,
            }

            # Check for common blocking indicators
            if response.status_code == 200:
                content = response.text.lower()
                if any(indicator in content for indicator in ["blocked", "forbidden", "access denied", "bot detected"]):
                    result["accessible"] = False
                    result["error"] = "Content suggests access is blocked"

        except requests.exceptions.Timeout:
            result = {
                "url": url,
                "status_code": None,
                "accessible": False,
                "response_time": None,
                "content_length": 0,
                "content_type": "",
                "error": "Request timeout",
            }
        except requests.exceptions.ConnectionError:
            result = {
                "url": url,
                "status_code": None,
                "accessible": False,
                "response_time": None,
                "content_length": 0,
                "content_type": "",
                "error": "Connection error",
            }
        except Exception as e:
            result = {
                "url": url,
                "status_code": None,
                "accessible": False,
                "response_time": None,
                "content_length": 0,
                "content_type": "",
                "error": str(e),
            }

        return result

    def test_all_crawlers(self, additional_pages=None):
        """Test access for all defined crawlers."""
        test_pages = TEST_PAGES.copy()
        if additional_pages:
            test_pages.extend(additional_pages)

        print(f"🧪 Testing crawler access to {self.base_url}")
        print(f"🎯 Testing {len(CRAWLER_USER_AGENTS)} crawlers on {len(test_pages)} pages")
        print("📋 EXPECTED RESULTS based on robots.txt:")
        print(
            "   ✅ SHOULD HAVE ACCESS: Googlebot, Bingbot, GPTBot, ClaudeBot, DuckDuckBot, CCBot, facebookexternalhit"
        )
        print(
            "   ❌ SHOULD BE BLOCKED: Google-Extended, Claude-Web, PerplexityBot, Bytespider, Twitterbot, LinkedInBot"
        )
        print("")

        for crawler_name, user_agent in CRAWLER_USER_AGENTS.items():
            self.test_crawler_access(crawler_name, user_agent, test_pages)

        return self.results

    def generate_report(self, output_file=None):
        """Generate a detailed report of crawler access results."""
        if not self.results:
            print("No test results available. Run tests first.")
            return None

        report = {
            "test_timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "summary": self._generate_summary(),
            "detailed_results": self.results,
        }

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\nDetailed report saved to: {output_file}")

        self._print_summary_report()
        return report

    def _generate_summary(self):
        """Generate summary statistics."""
        total_crawlers = len(self.results)
        fully_accessible = 0
        partially_blocked = 0
        fully_blocked = 0

        for crawler_name, results in self.results.items():
            accessible = results["summary"]["accessible"]
            total_pages = sum(results["summary"].values())

            if accessible == total_pages:
                fully_accessible += 1
            elif accessible == 0:
                fully_blocked += 1
            else:
                partially_blocked += 1

        return {
            "total_crawlers_tested": total_crawlers,
            "fully_accessible": fully_accessible,
            "partially_blocked": partially_blocked,
            "fully_blocked": fully_blocked,
        }

    def _print_summary_report(self):
        """Print a human-readable summary report."""
        print("\n" + "=" * 60)
        print("CRAWLER ACCESS TEST RESULTS")
        print("=" * 60)
        print("🧪 TESTING: Does GitHub Pages respect robots.txt restrictions?")

        summary = self._generate_summary()
        print(f"Base URL: {self.base_url}")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Show current robots.txt content
        try:
            robots_response = requests.get(f"{self.base_url}/robots.txt", timeout=10)
            if robots_response.status_code == 200:
                print("\nCURRENT ROBOTS.TXT CONTENT:")
                print("-" * 40)
                print(robots_response.text[:500] + ("..." if len(robots_response.text) > 500 else ""))
                print("-" * 40)
        except Exception:
            print("\n⚠️  Could not fetch robots.txt")

        print(f"Total Crawlers Tested: {summary['total_crawlers_tested']}")
        print(f"Fully Accessible: {summary['fully_accessible']}")
        print(f"Partially Blocked: {summary['partially_blocked']}")
        print(f"Fully Blocked: {summary['fully_blocked']}")

        print("\nDETAILED RESULTS:")
        print("-" * 60)

        for crawler_name, results in self.results.items():
            summary_stats = results["summary"]
            total_pages = sum(summary_stats.values())
            accessible_pages = summary_stats["accessible"]

            status = "✅ ACCESSIBLE"
            if accessible_pages == 0:
                status = "❌ BLOCKED"
            elif accessible_pages < total_pages:
                status = "⚠️  PARTIAL"

            print(f"{crawler_name:20} {status:12} ({accessible_pages}/{total_pages} pages)")

            # Show any specific issues
            for page, page_result in results["pages"].items():
                if not page_result["accessible"]:
                    error_info = page_result.get("error", f"HTTP {page_result['status_code']}")
                    print(f"  └─ {page}: {error_info}")

        print("\n🎯 RECOMMENDATIONS:")
        print("-" * 60)

        if summary["fully_blocked"] > 0:
            print("⚠️  Some crawlers are completely blocked. Consider:")
            print("   - 🔍 Checking if GitHub Pages has crawler restrictions")
            print("   - 🚀 Evaluating alternative hosting platforms")

        if summary["partially_blocked"] > 0:
            print("⚠️  Some crawlers have partial access issues. Review:")
            print("   - 📊 Specific page access patterns")
            print("   - 🔧 Server response codes and headers")

        if summary["fully_accessible"] == summary["total_crawlers_tested"]:
            print("🚨 ALL CRAWLERS HAVE FULL ACCESS - This means robots.txt Disallow rules are IGNORED!")


def discover_sample_pages(base_url):
    """Discover additional sample pages to test from sitemap."""
    additional_pages = []

    try:
        base_url_norm = base_url.rstrip("/") + "/"
        sitemap_url = urljoin(base_url_norm, "sitemap.xml")
        response = requests.get(sitemap_url, timeout=10)

        if response.status_code == 200:
            # Simple regex to extract URLs from sitemap
            import re

            urls = re.findall(r"<loc>(.*?)</loc>", response.text)

            # Convert absolute URLs to relative paths and take a sample
            for url in urls[:5]:  # Test first 5 pages
                if url.startswith(base_url_norm):
                    relative_path = url[len(base_url_norm) :].lstrip("/")
                    if relative_path and relative_path not in TEST_PAGES:
                        additional_pages.append(relative_path)

    except Exception as e:
        print(f"Could not discover additional pages from sitemap: {e}")

    return additional_pages


def main():
    """Main function to run crawler access tests."""
    # Get base URL from environment or use default
    site_domain = os.getenv("SITE_DOMAIN", "").strip()
    gh_username = os.getenv("GH_USERNAME", "").strip()

    if site_domain:
        base_url = f"https://{site_domain}"
    elif gh_username:
        base_url = f"https://{gh_username}.github.io/devto-mirror"
    else:
        print("Error: SITE_DOMAIN or GH_USERNAME environment variable must be set")
        sys.exit(1)

    # Allow override of base URL for testing
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    print(f"Testing crawler access for: {base_url}")

    # Initialize tester
    tester = CrawlerAccessTester(base_url)

    # Discover additional sample pages
    additional_pages = discover_sample_pages(base_url)
    if additional_pages:
        print(f"Discovered {len(additional_pages)} additional pages to test")

    # Run tests
    tester.test_all_crawlers(additional_pages)

    # Generate report
    output_file = "crawler_access_report.json"
    tester.generate_report(output_file)

    # Return exit code based on results
    summary = tester._generate_summary()
    if summary["fully_blocked"] > 0:
        print(f"\n⚠️  Warning: {summary['fully_blocked']} crawlers are fully blocked")
        sys.exit(1)
    elif summary["partially_blocked"] > 0:
        print(f"\n⚠️  Warning: {summary['partially_blocked']} crawlers have partial access")
        sys.exit(2)
    else:
        print("\n✅ All crawlers have full access")
        sys.exit(0)


if __name__ == "__main__":
    main()
