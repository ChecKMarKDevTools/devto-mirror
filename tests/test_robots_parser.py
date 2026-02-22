"""Tests for robots.txt parser module."""

import unittest

from devto_mirror.core.robots_parser import (
    _extract_sitemap,
    _parse_user_agent_line,
    _parse_user_agent_rules,
    _process_allow_rule,
    _process_disallow_rule,
    parse_robots_txt,
)


class TestRobotsParser(unittest.TestCase):
    """Test robots.txt parsing functionality."""

    def test_parse_robots_txt_universal_allow(self):
        """Test parsing robots.txt with universal allow."""
        content = """User-agent: *
Allow: /
Sitemap: https://example.com/sitemap.xml"""

        result = parse_robots_txt(content)

        self.assertEqual(result["content_length"], len(content))
        self.assertIn("/", result["universal_rules"]["allow"])
        self.assertEqual(result["sitemap_url"], "https://example.com/sitemap.xml")
        self.assertTrue(result["analysis"]["universal_allow"])
        self.assertFalse(result["analysis"]["has_restrictions"])

    def test_parse_robots_txt_with_disallow(self):
        """Test parsing robots.txt with disallow rules."""
        content = """User-agent: *
Disallow: /admin/
Disallow: /private/"""

        result = parse_robots_txt(content)

        self.assertIn("/admin/", result["universal_rules"]["disallow"])
        self.assertIn("/private/", result["universal_rules"]["disallow"])
        self.assertTrue(result["analysis"]["has_restrictions"])

    def test_parse_robots_txt_specific_agents(self):
        """Test parsing robots.txt with specific user agents."""
        content = """User-agent: Googlebot
Allow: /

User-agent: BadBot
Disallow: /"""

        result = parse_robots_txt(content)

        self.assertIn("Googlebot", result["allowed_agents"])
        self.assertIn("BadBot", result["disallowed_agents"])
        self.assertEqual(result["analysis"]["total_specific_agents"], 2)

    def test_parse_robots_txt_comments_and_empty_lines(self):
        """Test parsing robots.txt with comments and empty lines."""
        content = """# This is a comment
User-agent: *

# Another comment
Allow: /

"""

        result = parse_robots_txt(content)

        self.assertIn("/", result["universal_rules"]["allow"])

    def test_extract_sitemap(self):
        """Test extracting sitemap URL."""
        content = "Sitemap: https://example.com/sitemap.xml"
        sitemap = _extract_sitemap(content)
        self.assertEqual(sitemap, "https://example.com/sitemap.xml")

    def test_extract_sitemap_case_insensitive(self):
        """Test extracting sitemap URL with different case."""
        content = "SITEMAP: https://example.com/sitemap.xml"
        sitemap = _extract_sitemap(content)
        self.assertEqual(sitemap, "https://example.com/sitemap.xml")

    def test_extract_sitemap_not_found(self):
        """Test extracting sitemap when not present."""
        content = "User-agent: *\nAllow: /"
        sitemap = _extract_sitemap(content)
        self.assertIsNone(sitemap)

    def test_parse_user_agent_line_wildcard(self):
        """Test parsing wildcard user agent."""
        line = "User-agent: *"
        result = _parse_user_agent_line(line)
        self.assertEqual(result, ["*"])

    def test_parse_user_agent_line_specific(self):
        """Test parsing specific user agent."""
        line = "User-agent: Googlebot"
        result = _parse_user_agent_line(line)
        self.assertEqual(result, ["Googlebot"])

    def test_process_allow_rule_universal(self):
        """Test processing allow rule for universal agent."""
        allowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_allow_rule("Allow: /", ["*"], allowed_agents, universal_rules)
        self.assertIn("/", universal_rules["allow"])

    def test_process_allow_rule_specific(self):
        """Test processing allow rule for specific agent."""
        allowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_allow_rule("Allow: /", ["Googlebot"], allowed_agents, universal_rules)
        self.assertIn("Googlebot", allowed_agents)

    def test_process_disallow_rule_universal(self):
        """Test processing disallow rule for universal agent."""
        disallowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_disallow_rule("Disallow: /admin/", ["*"], disallowed_agents, universal_rules)
        self.assertIn("/admin/", universal_rules["disallow"])

    def test_process_disallow_rule_specific(self):
        """Test processing disallow rule for specific agent."""
        disallowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_disallow_rule("Disallow: /admin/", ["Googlebot"], disallowed_agents, universal_rules)
        self.assertIn("Googlebot", disallowed_agents)

    def test_process_disallow_rule_empty_path(self):
        """Test processing disallow rule with empty path."""
        disallowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_disallow_rule("Disallow: ", ["Googlebot"], disallowed_agents, universal_rules)
        self.assertNotIn("Googlebot", disallowed_agents)

    def test_process_allow_rule_empty_path(self):
        """Test processing allow rule with empty path for specific agent."""
        allowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_allow_rule("Allow: ", ["Googlebot"], allowed_agents, universal_rules)
        self.assertNotIn("Googlebot", allowed_agents)

    def test_process_allow_rule_empty_path_universal(self):
        """Test processing allow rule with empty path for universal agent."""
        allowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_allow_rule("Allow: ", ["*"], allowed_agents, universal_rules)
        # Empty paths are not recorded for consistency with Disallow behavior
        self.assertEqual(len(universal_rules["allow"]), 0)

    def test_process_disallow_rule_empty_path_universal(self):
        """Test processing disallow rule with empty path for universal agent."""
        disallowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_disallow_rule("Disallow: ", ["*"], disallowed_agents, universal_rules)
        # Empty paths are not recorded for consistency with Allow behavior
        self.assertEqual(len(universal_rules["disallow"]), 0)

    def test_process_allow_rule_no_agents(self):
        """Test processing allow rule when no user-agent has been declared."""
        allowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_allow_rule("Allow: /", [], allowed_agents, universal_rules)
        self.assertEqual(len(allowed_agents), 0)
        self.assertEqual(len(universal_rules["allow"]), 0)

    def test_process_disallow_rule_no_agents(self):
        """Test processing disallow rule when no user-agent has been declared."""
        disallowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_disallow_rule("Disallow: /admin/", [], disallowed_agents, universal_rules)
        self.assertEqual(len(disallowed_agents), 0)
        self.assertEqual(len(universal_rules["disallow"]), 0)

    def test_parse_robots_txt_rules_before_user_agent(self):
        """Test parsing robots.txt with rules before any User-agent directive."""
        # Rules before any User-agent directive should be silently ignored
        # because current_agents will be empty when they're processed
        content = """Allow: /public/
Disallow: /private/
User-agent: *
Allow: /"""

        result = parse_robots_txt(content)

        # Only the rule after User-agent should be recorded
        self.assertIn("/", result["universal_rules"]["allow"])
        # Rules before User-agent should be ignored
        self.assertNotIn("/public/", result["universal_rules"]["allow"])
        self.assertNotIn("/private/", result["universal_rules"]["disallow"])

    def test_parse_robots_txt_invalid_type(self):
        """Test that non-string input raises TypeError."""
        with self.assertRaises(TypeError) as context:
            parse_robots_txt(None)  # NOSONAR - intentional wrong type for error-path test
        self.assertIn("content must be a string", str(context.exception))

        with self.assertRaises(TypeError):
            parse_robots_txt(123)  # NOSONAR - intentional wrong type for error-path test

        with self.assertRaises(TypeError):
            parse_robots_txt([])  # NOSONAR - intentional wrong type for error-path test

    def test_parse_user_agent_line_malformed(self):
        """Test parsing malformed user-agent line without colon."""
        line = "User-agent"
        result = _parse_user_agent_line(line)
        self.assertEqual(result, [])

    def test_parse_user_agent_line_empty_value(self):
        """Test parsing user-agent line with empty value."""
        line = "User-agent: "
        result = _parse_user_agent_line(line)
        self.assertEqual(result, [])

    def test_process_allow_rule_malformed(self):
        """Test processing malformed allow rule without colon."""
        allowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_allow_rule("Allow", ["*"], allowed_agents, universal_rules)
        self.assertEqual(len(universal_rules["allow"]), 0)

    def test_process_disallow_rule_malformed(self):
        """Test processing malformed disallow rule without colon."""
        disallowed_agents = set()
        universal_rules = {"allow": [], "disallow": []}
        _process_disallow_rule("Disallow", ["*"], disallowed_agents, universal_rules)
        self.assertEqual(len(universal_rules["disallow"]), 0)

    def test_parse_robots_txt_different_line_endings(self):
        """Test parsing robots.txt with different line ending styles."""
        content_unix = "User-agent: *\nAllow: /\nDisallow: /admin/"
        content_windows = "User-agent: *\r\nAllow: /\r\nDisallow: /admin/"
        content_mac = "User-agent: *\rAllow: /\rDisallow: /admin/"

        result_unix = parse_robots_txt(content_unix)
        result_windows = parse_robots_txt(content_windows)
        result_mac = parse_robots_txt(content_mac)

        for result in [result_unix, result_windows, result_mac]:
            self.assertIn("/", result["universal_rules"]["allow"])
            self.assertIn("/admin/", result["universal_rules"]["disallow"])

    def test_parse_user_agent_rules_complex(self):
        """Test parsing complex user agent rules."""
        content = """User-agent: *
Allow: /
Disallow: /admin/

User-agent: Googlebot
Allow: /special/

User-agent: BadBot
Disallow: /"""

        allowed_agents, disallowed_agents, universal_rules = _parse_user_agent_rules(content)

        self.assertIn("/", universal_rules["allow"])
        self.assertIn("/admin/", universal_rules["disallow"])
        self.assertIn("Googlebot", allowed_agents)
        self.assertIn("BadBot", disallowed_agents)


if __name__ == "__main__":
    unittest.main()
