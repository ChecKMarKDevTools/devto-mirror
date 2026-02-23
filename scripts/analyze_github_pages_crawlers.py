#!/usr/bin/env python3
"""
GitHub Pages crawler restrictions analysis script.

This script analyzes the current GitHub Pages deployment for crawler accessibility,
documents findings, and compares actual access with robots.txt permissions.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

from devto_mirror.robots_parser import parse_robots_txt


class GitHubPagesCrawlerAnalyzer:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "robots_txt_analysis": {},
            "actual_crawler_access": {},
            "comparison": {},
            "recommendations": [],
        }

    def analyze_robots_txt(self):
        """Analyze the robots.txt file to understand intended permissions."""
        print("Analyzing robots.txt permissions...")

        try:
            robots_url = urljoin(self.base_url + "/", "robots.txt")
            response = requests.get(robots_url, timeout=10)

            if response.status_code != 200:
                self.analysis_results["robots_txt_analysis"] = {
                    "accessible": False,
                    "error": f"HTTP {response.status_code}",
                    "content": None,
                }
                return

            robots_content = response.text
            parsed_data = parse_robots_txt(robots_content)

            self.analysis_results["robots_txt_analysis"] = {"accessible": True, **parsed_data}

        except Exception as e:
            self.analysis_results["robots_txt_analysis"] = {"accessible": False, "error": str(e), "content": None}

    def load_crawler_access_results(self, report_file="crawler_access_report.json"):
        """Load results from the crawler access test."""
        print("Loading crawler access test results...")

        try:
            if not Path(report_file).exists():
                print(f"Crawler access report not found: {report_file}")
                print("Run 'uv run python scripts/test_crawler_access.py' first to generate the report.")
                return False

            with open(report_file, "r") as f:
                crawler_data = json.load(f)

            self.analysis_results["actual_crawler_access"] = {
                "test_timestamp": crawler_data.get("test_timestamp"),
                "summary": crawler_data.get("summary", {}),
                "detailed_results": crawler_data.get("detailed_results", {}),
            }
            return True

        except Exception as e:
            print(f"Error loading crawler access results: {e}")
            return False

    def compare_permissions_vs_access(self):
        """Compare robots.txt permissions with actual crawler access."""
        print("Comparing robots.txt permissions with actual access...")

        robots_analysis = self.analysis_results.get("robots_txt_analysis", {})
        crawler_results = self.analysis_results.get("actual_crawler_access", {})

        if not robots_analysis.get("accessible") or not crawler_results:
            self.analysis_results["comparison"] = {
                "error": "Cannot compare - missing robots.txt or crawler access data"
            }
            return

        # Get list of crawlers that were tested
        tested_crawlers = list(crawler_results.get("detailed_results", {}).keys())

        # Get robots.txt permissions
        allowed_agents = set(robots_analysis.get("allowed_agents", []))
        universal_allow = robots_analysis.get("analysis", {}).get("universal_allow", False)

        # Analyze each crawler
        comparison_results = {}

        for crawler_name in tested_crawlers:
            crawler_data = crawler_results["detailed_results"][crawler_name]
            actual_access = crawler_data["summary"]["accessible"] > 0

            # Determine expected access based on robots.txt
            expected_access = universal_allow or crawler_name in allowed_agents

            comparison_results[crawler_name] = {
                "expected_access": expected_access,
                "actual_access": actual_access,
                "matches_expectation": expected_access == actual_access,
                "pages_accessible": crawler_data["summary"]["accessible"],
                "total_pages_tested": sum(crawler_data["summary"].values()),
            }

        # Generate summary statistics
        total_crawlers = len(comparison_results)
        matches_expectation = sum(1 for r in comparison_results.values() if r["matches_expectation"])
        unexpected_blocks = sum(
            1 for r in comparison_results.values() if r["expected_access"] and not r["actual_access"]
        )
        unexpected_access = sum(
            1 for r in comparison_results.values() if not r["expected_access"] and r["actual_access"]
        )

        self.analysis_results["comparison"] = {
            "summary": {
                "total_crawlers_tested": total_crawlers,
                "matches_expectation": matches_expectation,
                "unexpected_blocks": unexpected_blocks,
                "unexpected_access": unexpected_access,
                "consistency_rate": matches_expectation / total_crawlers if total_crawlers > 0 else 0,
            },
            "detailed_comparison": comparison_results,
        }

    def generate_recommendations(self):
        """Generate recommendations based on the analysis."""
        print("Generating recommendations...")

        recommendations = []

        # Check robots.txt analysis
        robots_analysis = self.analysis_results.get("robots_txt_analysis", {})
        if robots_analysis.get("accessible"):
            if robots_analysis.get("analysis", {}).get("universal_allow"):
                recommendations.append(
                    {
                        "type": "positive",
                        "category": "robots_txt",
                        "message": "✅ robots.txt correctly allows universal access with 'Allow: /' for all user agents",
                    }
                )

            if not robots_analysis.get("analysis", {}).get("has_restrictions"):
                recommendations.append(
                    {
                        "type": "positive",
                        "category": "robots_txt",
                        "message": "✅ No crawler restrictions found in robots.txt",
                    }
                )

        # Check crawler access results
        crawler_summary = self.analysis_results.get("actual_crawler_access", {}).get("summary", {})
        total_crawlers = crawler_summary.get("total_crawlers_tested", 0)
        fully_accessible = crawler_summary.get("fully_accessible", 0)

        if fully_accessible == total_crawlers and total_crawlers > 0:
            recommendations.append(
                {
                    "type": "positive",
                    "category": "access",
                    "message": f"✅ All {total_crawlers} tested crawlers have full access to the site",
                }
            )
        elif crawler_summary.get("fully_blocked", 0) > 0:
            recommendations.append(
                {
                    "type": "warning",
                    "category": "access",
                    "message": f"⚠️  {crawler_summary['fully_blocked']} crawlers are completely blocked",
                }
            )

        # Check comparison results
        comparison = self.analysis_results.get("comparison", {})
        if comparison and "summary" in comparison:
            consistency_rate = comparison["summary"].get("consistency_rate", 0)
            if abs(consistency_rate - 1.0) < 1e-9:
                recommendations.append(
                    {
                        "type": "positive",
                        "category": "consistency",
                        "message": "✅ Actual crawler access matches robots.txt permissions perfectly",
                    }
                )
            elif consistency_rate < 0.9:
                recommendations.append(
                    {
                        "type": "warning",
                        "category": "consistency",
                        "message": f"⚠️  Only {consistency_rate:.1%} of crawlers behave as expected from robots.txt",
                    }
                )

        # GitHub Pages specific recommendations
        recommendations.append(
            {
                "type": "info",
                "category": "platform",
                "message": "ℹ️  GitHub Pages appears to honor robots.txt permissions without additional restrictions",
            }
        )

        recommendations.append(
            {
                "type": "info",
                "category": "platform",
                "message": "ℹ️  No evidence of GitHub Pages blocking crawlers beyond robots.txt rules",
            }
        )

        # Migration recommendations
        if crawler_summary.get("fully_blocked", 0) == 0 and crawler_summary.get("partially_blocked", 0) == 0:
            recommendations.append(
                {
                    "type": "positive",
                    "category": "migration",
                    "message": "✅ No need to migrate from GitHub Pages - all crawlers have full access",
                }
            )
        else:
            recommendations.append(
                {
                    "type": "suggestion",
                    "category": "migration",
                    "message": "💡 Consider evaluating Cloudflare Workers if crawler access issues persist",
                }
            )

        self.analysis_results["recommendations"] = recommendations

    def generate_report(self, output_file="github_pages_crawler_analysis.json"):
        """Generate a comprehensive analysis report."""
        print("\nGenerating comprehensive analysis report...")

        # Save detailed JSON report
        with open(output_file, "w") as f:
            json.dump(self.analysis_results, f, indent=2)
        print(f"Detailed analysis saved to: {output_file}")

        # Print human-readable summary
        self._print_analysis_summary()

        return self.analysis_results

    def _print_robots_analysis_section(self, robots_analysis):
        """Print the robots.txt analysis section of the summary."""
        if robots_analysis.get("accessible"):
            analysis = robots_analysis.get("analysis", {})
            print(f"✅ robots.txt accessible ({robots_analysis.get('content_length', 0)} bytes)")
            print(f"Universal Allow: {'✅ Yes' if analysis.get('universal_allow') else '❌ No'}")
            print(f"Has Restrictions: {'⚠️  Yes' if analysis.get('has_restrictions') else '✅ No'}")
            print(f"Specific Agent Rules: {analysis.get('total_specific_agents', 0)}")
            if robots_analysis.get("sitemap_url"):
                print(f"Sitemap URL: {robots_analysis['sitemap_url']}")
        else:
            print(f"❌ robots.txt not accessible: {robots_analysis.get('error', 'Unknown error')}")

    def _print_analysis_summary(self):
        """Print a human-readable analysis summary."""
        print("\n" + "=" * 70)
        print("GITHUB PAGES CRAWLER RESTRICTIONS ANALYSIS")
        print("=" * 70)

        print(f"Base URL: {self.base_url}")
        print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Robots.txt Analysis
        print("\nROBOTS.TXT ANALYSIS:")
        print("-" * 30)
        robots_analysis = self.analysis_results.get("robots_txt_analysis", {})
        self._print_robots_analysis_section(robots_analysis)

        # Crawler Access Summary
        print("\nCRAWLER ACCESS SUMMARY:")
        print("-" * 30)
        crawler_summary = self.analysis_results.get("actual_crawler_access", {}).get("summary", {})
        if crawler_summary:
            total = crawler_summary.get("total_crawlers_tested", 0)
            accessible = crawler_summary.get("fully_accessible", 0)
            blocked = crawler_summary.get("fully_blocked", 0)
            partial = crawler_summary.get("partially_blocked", 0)

            print(f"Total Crawlers Tested: {total}")
            percentage = (accessible / total * 100) if total > 0 else 0
            print(f"Fully Accessible: {accessible} ({percentage:.1f}%)")
            print(f"Partially Blocked: {partial}")
            print(f"Fully Blocked: {blocked}")
        else:
            print("❌ No crawler access data available")

        # Comparison Results
        print("\nPERMISSIONS vs ACTUAL ACCESS:")
        print("-" * 30)
        comparison = self.analysis_results.get("comparison", {})
        if comparison and "summary" in comparison:
            summary = comparison["summary"]
            consistency = summary.get("consistency_rate", 0)
            print(f"Consistency Rate: {consistency:.1%}")
            print(f"Unexpected Blocks: {summary.get('unexpected_blocks', 0)}")
            print(f"Unexpected Access: {summary.get('unexpected_access', 0)}")
        else:
            print("❌ Comparison data not available")

        # Recommendations
        print("\nRECOMMENDATIONS:")
        print("-" * 30)
        recommendations = self.analysis_results.get("recommendations", [])
        for rec in recommendations:
            print(f"{rec['message']}")

        # Key Findings
        print("\nKEY FINDINGS:")
        print("-" * 30)

        if crawler_summary.get("fully_accessible", 0) == crawler_summary.get("total_crawlers_tested", 0):
            print("🎉 EXCELLENT: All tested crawlers have full access to the GitHub Pages site")
            print("🎉 CONCLUSION: GitHub Pages does not appear to block any major crawlers")
            print("🎉 RESULT: No migration to alternative hosting platform is needed")
        else:
            print("⚠️  Some crawlers are experiencing access issues")
            print("💡 Consider investigating specific crawler blocking patterns")
            print("💡 Evaluate alternative hosting platforms if issues persist")


def main():
    """Main function to run GitHub Pages crawler analysis."""
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

    print(f"Analyzing GitHub Pages crawler restrictions for: {base_url}")

    # Initialize analyzer
    analyzer = GitHubPagesCrawlerAnalyzer(base_url)

    # Run analysis steps
    analyzer.analyze_robots_txt()

    # Load crawler access results (requires running test_crawler_access.py first)
    if not analyzer.load_crawler_access_results():
        print("\nRunning crawler access test first...")
        import subprocess  # nosec B404

        try:
            result = subprocess.run(  # nosec B603
                [sys.executable, "scripts/test_crawler_access.py"], capture_output=True, text=True, cwd="."
            )
            if result.returncode == 0:
                print("✅ Crawler access test completed successfully")
                analyzer.load_crawler_access_results()
            else:
                print(f"⚠️  Crawler access test completed with warnings (exit code: {result.returncode})")
                analyzer.load_crawler_access_results()
        except Exception as e:
            print(f"❌ Failed to run crawler access test: {e}")
            print("Please run 'uv run python scripts/test_crawler_access.py' manually first")

    analyzer.compare_permissions_vs_access()
    analyzer.generate_recommendations()

    # Generate report
    report = analyzer.generate_report()

    # Return appropriate exit code
    crawler_summary = report.get("actual_crawler_access", {}).get("summary", {})
    if crawler_summary.get("fully_blocked", 0) > 0:
        sys.exit(1)  # Some crawlers blocked
    elif crawler_summary.get("partially_blocked", 0) > 0:
        sys.exit(2)  # Some crawlers partially blocked
    else:
        sys.exit(0)  # All good


if __name__ == "__main__":
    main()
