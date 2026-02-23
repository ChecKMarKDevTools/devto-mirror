#!/usr/bin/env python3

"""Run pip-audit with a hard timeout.

Problem:
- `pip-audit` can hang indefinitely on network calls (PyPI / advisory sources),
  which blocks `make security` and therefore `make ai-checks` and lefthook.

Policy:
- In CI (CI=true or GITHUB_ACTIONS=true) we stay strict: failure/timeout exits non-zero.
- Locally we prefer developer-flow: timeout/error prints a warning and exits 0.

Controls:
- PIP_AUDIT_TIMEOUT_SECONDS: int, default 120 in CI/strict mode, 15 locally
- PIP_AUDIT_STRICT: if set to "1" forces strict mode even outside CI
"""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys


def _is_strict() -> bool:
    if os.getenv("PIP_AUDIT_STRICT") == "1":
        return True
    return os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"


def _run_pip_audit(cmd: list, timeout_seconds: int, strict: bool) -> "subprocess.CompletedProcess | int":
    """Run pip-audit subprocess, returning CompletedProcess or an int exit code on error."""
    try:
        return subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "WARNING: pip-audit was interrupted (likely a long-running network call).",
            file=sys.stderr,
        )
    except subprocess.TimeoutExpired:
        msg = (
            f"WARNING: pip-audit timed out after {timeout_seconds}s. "
            "Set PIP_AUDIT_TIMEOUT_SECONDS to raise/lower this."
        )
        print(msg, file=sys.stderr)
    except Exception as e:
        print(f"WARNING: pip-audit failed to run: {e}", file=sys.stderr)
    return 1 if strict else 0


def main() -> int:
    strict = _is_strict()

    try:
        default_timeout = "120" if strict else "15"
        timeout_seconds = int(os.getenv("PIP_AUDIT_TIMEOUT_SECONDS", default_timeout))
    except ValueError:
        timeout_seconds = 120 if strict else 15

    print(
        f"pip-audit: running with timeout={timeout_seconds}s (strict={'yes' if strict else 'no'})",
        file=sys.stderr,
    )

    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "--progress-spinner=off",
        "--skip-editable",
    ]

    result = _run_pip_audit(cmd, timeout_seconds, strict)
    if isinstance(result, int):
        return result

    # pip-audit return codes:
    # - 0: no vulns
    # - non-zero: vulns found or failure
    if result.returncode != 0:
        print("pip-audit reported issues:")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode if strict else 0

    print("pip-audit: No vulnerabilities found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
