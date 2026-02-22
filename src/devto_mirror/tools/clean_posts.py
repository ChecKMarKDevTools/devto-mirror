#!/usr/bin/env python3
"""
Clean posts_data.json by deduplicating entries that share the same canonical link or slug.
Keeps the newest post when duplicates are found (based on parsed date), backs up the original file.

Usage: python -m scripts.clean_posts_data
"""

import json
from datetime import datetime
from pathlib import Path

from devto_mirror.core.constants import POSTS_DATA_FILE
from devto_mirror.core.utils import parse_date

ROOT = Path(__file__).resolve().parents[3]


def _safe_path(path: Path) -> Path:
    """Resolve path and validate it stays within ROOT to prevent path traversal."""
    resolved = path.resolve()
    if not str(resolved).startswith(str(ROOT.resolve())):
        raise ValueError(f"Path traversal detected: {resolved!r} is outside repo root")
    return resolved


DATA_FILE = _safe_path(ROOT / POSTS_DATA_FILE)
BACKUP_FILE = _safe_path(ROOT / f"{POSTS_DATA_FILE}.bak")


def key_for(post):
    # Prefer canonical link if present, else slug
    link = post.get("link") or ""
    slug = post.get("slug") or ""
    # normalize by stripping trailing slash
    if link.endswith("/"):
        link = link[:-1]
    return link or slug


def dedupe_posts(data):
    groups = {}
    for p in data:
        k = key_for(p)
        if not k:
            # fallback: use title
            k = p.get("title", "")
        existing = groups.get(k)
        if not existing:
            groups[k] = p
            continue
        # compare dates, prefer newest
        a = parse_date(existing.get("date"))
        b = parse_date(p.get("date"))
        if a is None and b is None:
            # keep existing
            continue
        if a is None:
            groups[k] = p
            continue
        if b is None:
            continue
        if b > a:
            groups[k] = p
    return list(groups.values())


def main():
    if not DATA_FILE.exists():
        print(f"No {POSTS_DATA_FILE} found at {DATA_FILE}")
        return
    data = json.loads(DATA_FILE.read_text())
    print(f"Loaded {len(data)} posts from {DATA_FILE}")

    # backup
    if not BACKUP_FILE.exists():
        BACKUP_FILE.write_text(DATA_FILE.read_text())
        print(f"Backed up original to {BACKUP_FILE}")

    cleaned = dedupe_posts(data)
    print(f"Deduped to {len(cleaned)} unique posts")
    # sort newest-first

    def _entry_date_key(x):
        return parse_date(x.get("date")) or datetime.min

    cleaned.sort(key=_entry_date_key, reverse=True)

    DATA_FILE.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
    print(f"Wrote cleaned {POSTS_DATA_FILE} ({len(cleaned)} posts)")


if __name__ == "__main__":
    main()
