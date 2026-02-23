#!/usr/bin/env python3
"""Validate commit message header for Conventional Commits compliance.

This script will try to run `gitlint` if available. If `gitlint` is not
installed, it falls back to a conservative, small regex that enforces
Conventional Commit headers for common types.
"""

import re
import subprocess  # nosec
import sys
from shutil import which

ALLOWED_TYPES = (
    "feat",
    "fix",
    "refactor",
    "perf",
    "test",
    "cicd",
    "docs",
    "style",
    "build",
    "chore",
)

# Known footer tokens
BREAKING_CHANGE_TOKEN = "BREAKING CHANGE"  # nosec
BREAKING_CHANGE_PREFIX = BREAKING_CHANGE_TOKEN + ":"


def run_gitlint(msgfile: str) -> int:
    """Run gitlint if available and return its exit code (0=ok).

    Return non-zero if gitlint reports issues or is not invokable.
    """
    gitlint_cmd = which("gitlint")
    if gitlint_cmd:
        return subprocess.call([gitlint_cmd, "--msg-filename", msgfile])  # nosec
    # try module invocation as fallback
    try:
        return subprocess.call([sys.executable, "-m", "gitlint", "--msg-filename", msgfile])  # nosec
    except Exception:
        return 2


def _find_header_and_strip(lines):
    # Remove trailing blank lines
    while lines and lines[-1].strip() == "":
        lines.pop()
    for i, line in enumerate(lines):
        if line.strip() != "":
            return i
    return None


def _validate_header(header: str) -> bool:
    type_part = "|".join(ALLOWED_TYPES)
    header_re = re.compile(rf"^({type_part})(?:\([A-Za-z0-9_\-:.]+\))?:\s+[A-Z][\s\S]{{0,71}}$")
    if not header_re.match(header):
        print("Invalid commit header:", header, file=sys.stderr)
        print("Expected: type(scope)?: Subject—where type is one of:", file=sys.stderr)
        print(", ".join(ALLOWED_TYPES), file=sys.stderr)
        return False
    return True


def _split_body_and_footers(lines, header_idx):
    body_start = header_idx + 2
    end_idx = len(lines) - 1
    # Collect footer-like lines from file end upwards
    footer_idx = None
    i = end_idx
    while i >= body_start:
        if re.match(r"^[A-Za-z0-9\- ]+:\s", lines[i].strip()):
            footer_idx = i
            i -= 1
            continue
        break
    if footer_idx is None:
        return lines[body_start : end_idx + 1], []
    # footers are contiguous from footer_idx..end_idx
    footers = [lines[k].strip() for k in range(footer_idx, end_idx + 1)]
    # ensure a blank line between body and footer
    if footer_idx - 1 < body_start or lines[footer_idx - 1].strip() != "":
        print(
            "Footer block must be separated from the body by a single blank line",
            file=sys.stderr,
        )
        return None, None
    body = lines[body_start : footer_idx - 1 + 1]
    return body, footers


def _validate_body(body_lines) -> bool:
    if not body_lines or all(line.strip() == "" for line in body_lines):
        print("Missing commit body; expected bulleted list of changes", file=sys.stderr)
        return False
    if not any(line.strip().startswith("- ") for line in body_lines if line.strip()):
        print(
            'Commit body must contain at least one bulleted change line starting with "- "',
            file=sys.stderr,
        )
        return False
    for ln in body_lines:
        if len(ln) > 100:
            print("Body line exceeds 100 characters:", ln, file=sys.stderr)
            return False
    return True


def _parse_footer_line(f):
    if ":" not in f:
        return None, None
    token, value = [p.strip() for p in f.split(":", 1)]
    return token, value


def _validate_person_footer(value) -> bool:
    return bool(re.match(r"^[^<]+ <[^>]+>$", value))


def _validate_commit_generated_by(value) -> bool:
    if not _validate_person_footer(value):
        print("Commit-generated-by must be in form: Name <email>", file=sys.stderr)
        return False
    return True


def _validate_reviewed_by(value) -> bool:
    if not _validate_person_footer(value):
        raise ValueError("Reviewed-by must be in form: Name <email>")
    return True


def _validate_co_authored_by(value) -> bool:
    if not _validate_person_footer(value):
        raise ValueError("Co-authored-by must be in form: Name <email>")
    return True


def _parse_footers_list(flist):
    parsed = []
    for f in flist:
        if f.startswith(BREAKING_CHANGE_PREFIX):
            parsed.append((BREAKING_CHANGE_TOKEN, f.split(":", 1)[1].strip()))
            continue
        token, value = _parse_footer_line(f)
        if not token:
            raise ValueError("Footer line missing colon separator: " + f)
        parsed.append((token, value))
    return parsed


def _validate_footers(footers) -> bool:
    if not footers:
        return True

    try:
        parsed = _parse_footers_list(footers)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return False

    # BREAKING CHANGE must be first footer if present
    if any(t == BREAKING_CHANGE_TOKEN for t, _ in parsed) and parsed[0][0] != BREAKING_CHANGE_TOKEN:
        print(
            "BREAKING CHANGE: footer must appear as the first footer line",
            file=sys.stderr,
        )
        return False

    try:
        for token, value in parsed:
            if token == BREAKING_CHANGE_TOKEN:
                if not value:
                    print("BREAKING CHANGE footer must include a description", file=sys.stderr)
                    return False
                continue
            if token not in FOOTER_VALIDATORS:
                print("Unknown footer token:", token, file=sys.stderr)
                return False
            ok = FOOTER_VALIDATORS[token](value)
            if not ok:
                return False
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return False
    return True


FOOTER_VALIDATORS = {
    "Commit-generated-by": _validate_commit_generated_by,
    "Assisted-by": bool,
    "Co-authored-by": _validate_co_authored_by,
    "Generated-by": bool,
    "Authored-by": bool,
    "Reviewed-by": _validate_reviewed_by,
    "Fixes": bool,
    "Closes": bool,
    "Resolves": bool,
    "Related": bool,
    "References": bool,
    BREAKING_CHANGE_TOKEN: bool,
}
KNOWN_KEYS = set(FOOTER_VALIDATORS.keys())


def full_conventional_check(msgfile: str) -> bool:
    with open(msgfile, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    header_idx = _find_header_and_strip(lines)
    if header_idx is None:
        print("Empty commit message", file=sys.stderr)
        return False
    header = lines[header_idx].strip()
    if not _validate_header(header):
        return False
    # Require blank line after header
    if header_idx + 1 >= len(lines) or lines[header_idx + 1].strip() != "":
        print("Missing blank line after commit header", file=sys.stderr)
        return False
    body, footers = _split_body_and_footers(lines, header_idx)
    if body is None:
        return False
    if not _validate_body(body):
        return False
    if not _validate_footers(footers):
        return False
    return True


def main(argv):
    if len(argv) < 2:
        print("Usage: validate_commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 2

    msgfile = argv[1]
    # Run gitlint if available—require it to pass when present
    gitlint_rc = run_gitlint(msgfile)
    if gitlint_rc != 0:
        print("gitlint reported issues (rc=" + str(gitlint_rc) + ")", file=sys.stderr)
        return gitlint_rc

    # Always run the full conventional checks (header, body bullets, footers)
    if full_conventional_check(msgfile):
        print("Commit message validation passed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
