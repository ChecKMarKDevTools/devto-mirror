#!/usr/bin/env bash
# scripts/prechecks.sh - minimal staged-file prechecks (POC)
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

# Expect staged filenames as positional args. Exit success if none provided.
if [[ $# -eq 0 ]]; then
  echo "No files provided to prechecks; exiting success."
  exit 0
fi

FILES=("$@")
echo "Prechecks target files:"
for f in "${FILES[@]}"; do echo "  - $f"; done

EXIT_CODE=0

# Gather Python files
PY_FILES=()
for f in "${FILES[@]}"; do
  [[ "${f##*.}" == "py" ]] && PY_FILES+=("$f") || true
done

# 1) Format (black + isort)—attempt fixes; do not fail the run
if [[ ${#PY_FILES[@]} -gt 0 ]]; then
  echo "Formatting Python files (black, isort)..."
  uv run black "${PY_FILES[@]}" --line-length 120 || true
  uv run isort "${PY_FILES[@]}" --profile black --line-length 120 || true

  # If running inside a git repo, stage any formatted changes so the commit includes them.
  if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Staging formatted Python files..."
    # Only add files that still exist
    EXISTING=()
    for f in "${PY_FILES[@]}"; do
      [[ -f "$f" ]] && EXISTING+=("$f") || true
    done
    if [[ ${#EXISTING[@]} -gt 0 ]]; then
      git add "${EXISTING[@]}" || true
      echo "Staged: ${EXISTING[*]}"
    fi
  fi
else
  echo "No Python files to format."
fi

# 2) Lint (flake8)—failures are critical
if [[ ${#PY_FILES[@]} -gt 0 ]]; then
  echo "Running flake8 on Python files..."
  if ! uv run flake8 "${PY_FILES[@]}"; then
    echo "flake8: issues detected" >&2
    EXIT_CODE=1
  fi
else
  echo "No Python files to lint."
fi

# 3) pip-audit: only if dependency files present among args
NEEDS_PIP_AUDIT=false
for f in "${FILES[@]}"; do
  case "$f" in
    pyproject.toml|uv.lock) NEEDS_PIP_AUDIT=true; break ;;
    *) ;;
  esac
done
if [[ "$NEEDS_PIP_AUDIT" == true ]]; then
  echo "Running pip-audit (dependency files changed)..."
  if ! uv run pip-audit --progress-spinner=off --skip-editable; then
    echo "pip-audit: vulnerabilities found or audit failed" >&2
    EXIT_CODE=1
  fi
else
  echo "No dependency files changed—skipping pip-audit."
fi

# 4) bandit: only run on explicit files under src/ or scripts/
BANDIT_FILES=()
for f in "${FILES[@]}"; do
  case "$f" in
    src/*.py|scripts/*.py) BANDIT_FILES+=("$f") ;;
    *) ;;
  esac
done
if [[ ${#BANDIT_FILES[@]} -gt 0 ]]; then
  echo "Running bandit on changed source files..."
  if ! uv run bandit -ll -iii "${BANDIT_FILES[@]}"; then
    echo "bandit: issues detected" >&2
    EXIT_CODE=1
  fi
else
  echo "No source files for bandit—skipping bandit."
fi

# 5) Unit tests: only if changes touch src/ or tests/
NEEDS_TESTS=false
for f in "${FILES[@]}"; do
  case "$f" in
    src/*|tests/*) NEEDS_TESTS=true; break ;;
    *) ;;
  esac
done
if [[ "$NEEDS_TESTS" == true ]]; then
  echo "Running unit tests (changes include src/ or tests/)..."
  if ! uv run python -m unittest discover -s tests -p 'test_*.py'; then
    echo "Unit tests failed" >&2
    EXIT_CODE=1
  fi
else
  echo "No changes under src/ or tests/—skipping unit tests."
fi

if [[ $EXIT_CODE -eq 0 ]]; then
  echo "PRECHECKS: all checks passed"
else
  echo "PRECHECKS: one or more checks failed (exit code: $EXIT_CODE)" >&2
fi

exit $EXIT_CODE
