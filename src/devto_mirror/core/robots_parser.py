"""Robots.txt parsing utilities."""

import re


def parse_robots_txt(content: str) -> dict[str, int | list[str] | dict | str | None]:
    """
    Parse robots.txt content and extract permissions.

    Args:
        content: Raw robots.txt content as string

    Returns:
        Dictionary containing parsed rules and analysis with keys:
        - content_length: int
        - allowed_agents: list[str]
        - disallowed_agents: list[str]
        - universal_rules: dict[str, list[str]]
        - sitemap_url: str | None
        - analysis: dict[str, bool | int]

    Raises:
        TypeError: If content is not a string

    Note:
        - Rules before User-agent directives are silently ignored
        - Empty Allow/Disallow paths are ignored for both specific and universal agents
        - Comments and empty lines are skipped
    """
    if not isinstance(content, str):
        raise TypeError(f"content must be a string, got {type(content).__name__} instead")

    allowed_agents, disallowed_agents, universal_rules = _parse_user_agent_rules(content)
    sitemap_url = _extract_sitemap(content)

    return {
        "content_length": len(content),
        "allowed_agents": list(allowed_agents),
        "disallowed_agents": list(disallowed_agents),
        "universal_rules": universal_rules,
        "sitemap_url": sitemap_url,
        "analysis": {
            "universal_allow": "/" in universal_rules["allow"],
            "has_restrictions": bool(disallowed_agents or universal_rules["disallow"]),
            "total_specific_agents": len(allowed_agents) + len(disallowed_agents),
        },
    }


def _parse_user_agent_rules(content: str) -> tuple[set[str], set[str], dict[str, list[str]]]:
    """
    Parse user agent rules from robots.txt content.

    Args:
        content: Raw robots.txt content

    Returns:
        Tuple of (allowed_agents, disallowed_agents, universal_rules) where:
        - allowed_agents: set of agent names with specific allow rules
        - disallowed_agents: set of agent names with specific disallow rules
        - universal_rules: dict with 'allow' and 'disallow' keys mapping to path lists
    """
    allowed_agents = set()
    disallowed_agents = set()
    universal_rules = {"allow": [], "disallow": []}
    current_agents = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("user-agent:"):
            current_agents = _parse_user_agent_line(line)
        elif line.lower().startswith("allow:"):
            # Allow/Disallow before any User-agent directive are silently ignored
            # because current_agents will be empty
            _process_allow_rule(line, current_agents, allowed_agents, universal_rules)
        elif line.lower().startswith("disallow:"):
            _process_disallow_rule(line, current_agents, disallowed_agents, universal_rules)

    return allowed_agents, disallowed_agents, universal_rules


def _parse_user_agent_line(line: str) -> list[str]:
    """
    Extract user agent from line.

    Args:
        line: User-agent directive line

    Returns:
        List containing ["*"] for wildcard, [agent_name] for specific agent,
        or [] if line is malformed (missing colon) or has empty value

    Note:
        Malformed lines without a colon separator are handled gracefully by
        returning an empty list, causing subsequent rules to be ignored until
        a valid User-agent directive is encountered.
    """
    parts = line.split(":", 1)
    if len(parts) < 2:
        return []
    agent = parts[1].strip()
    if agent == "*":
        return ["*"]
    if agent:
        return [agent]
    return []


def _parse_directive_value(line: str) -> str | None:
    """
    Extract the value (path) from an Allow or Disallow directive.

    Args:
        line: Directive line (e.g., "Allow: /path" or "Disallow: /admin")

    Returns:
        Stripped path value, or None if line is malformed (missing colon)
    """
    parts = line.split(":", 1)
    if len(parts) < 2:
        return None
    return parts[1].strip()


def _process_allow_rule(line: str, current_agents: list[str], allowed_agents: set, universal_rules: dict) -> None:
    """
    Process an Allow directive.

    Args:
        line: Allow directive line
        current_agents: List of current user agents
        allowed_agents: Set of agents with specific allow rules
        universal_rules: Dictionary of universal allow/disallow rules

    Note:
        Returns early if:
        - No user agents have been declared (current_agents is empty)
        - Line is malformed (missing colon separator)
        - Path is empty (empty paths are not recorded for consistency with Disallow)
    """
    if not current_agents:
        return

    path = _parse_directive_value(line)
    if path is None:
        return

    # Empty paths are ignored for consistency with Disallow behavior
    if not path:
        return

    if "*" in current_agents:
        universal_rules["allow"].append(path)
    else:
        for agent in current_agents:
            allowed_agents.add(agent)


def _process_disallow_rule(line: str, current_agents: list[str], disallowed_agents: set, universal_rules: dict) -> None:
    """
    Process a Disallow directive.

    Args:
        line: Disallow directive line
        current_agents: List of current user agents
        disallowed_agents: Set of agents with specific disallow rules
        universal_rules: Dictionary of universal allow/disallow rules

    Note:
        Returns early if:
        - No user agents have been declared (current_agents is empty)
        - Line is malformed (missing colon separator)
        - Path is empty (empty paths are not recorded for consistency with Allow)

        Note: In robots.txt standard, an empty Disallow means "allow everything",
        but we don't record it to maintain consistency with Allow behavior.
    """
    if not current_agents:
        return

    path = _parse_directive_value(line)
    if path is None:
        return

    # Empty paths are ignored for consistency with Allow behavior
    if not path:
        return

    if "*" in current_agents:
        universal_rules["disallow"].append(path)
    else:
        for agent in current_agents:
            disallowed_agents.add(agent)


def _extract_sitemap(content: str) -> str | None:
    """
    Extract sitemap URL from robots.txt content.

    Args:
        content: Raw robots.txt content

    Returns:
        Sitemap URL if found, None otherwise
    """
    sitemap_match = re.search(r"Sitemap:\s*(.+)", content, re.IGNORECASE)
    return sitemap_match.group(1).strip() if sitemap_match else None
