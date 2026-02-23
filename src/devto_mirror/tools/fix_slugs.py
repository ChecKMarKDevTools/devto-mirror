#!/usr/bin/env python3
"""
Fix slug truncation in posts_data.json by extracting full slugs from URLs.
This script fixes the issue where slugs were truncated and missing Dev.to post IDs.

Usage: python3 scripts/fix_slugs.py
"""

import json
import pathlib


def extract_slug_from_url(url):
    """Extract the full slug from a Dev.to URL"""
    if not url or "//" not in url:
        return None

    try:
        # Extract the path part after the protocol
        url_path = url.split("//")[1]  # Remove protocol
        path_parts = url_path.split("/")
        if len(path_parts) >= 3:  # domain, username, slug
            return path_parts[2]  # The full slug with ID
    except (IndexError, ValueError):
        # Failed to parse URL structure
        return None

    return None


def _safe_path(path: pathlib.Path, base: pathlib.Path) -> pathlib.Path:
    """Resolve path and validate it stays within base to prevent path traversal."""
    resolved = path.resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise ValueError(f"Path traversal detected: {resolved!r} is outside {base!r}")
    return resolved


def main():
    """Fix slugs in posts_data.json"""
    base_dir = pathlib.Path.cwd()
    posts_file = _safe_path(base_dir / "posts_data.json", base_dir)

    if not posts_file.exists():
        print("No posts_data.json found. Nothing to fix.")
        return

    # Backup the original file
    backup_file = _safe_path(base_dir / "posts_data.json.backup", base_dir)
    if not backup_file.exists():
        backup_file.write_text(posts_file.read_text(), encoding="utf-8")
        print("Created backup: posts_data.json.backup")

    # Load the data
    try:
        with posts_file.open("r", encoding="utf-8") as f:
            posts = json.load(f)
    except Exception as e:
        print(f"Error loading posts_data.json: {e}")
        return

    print(f"Loaded {len(posts)} posts")

    fixed_count = 0
    for post in posts:
        url = post.get("link", "")
        current_slug = post.get("slug", "")

        if url:
            correct_slug = extract_slug_from_url(url)
            if correct_slug and correct_slug != current_slug:
                print("Fixing slug:")
                print(f"  Title: {post.get('title', 'Untitled')}")
                print(f"  Old slug: {current_slug}")
                print(f"  New slug: {correct_slug}")
                post["slug"] = correct_slug
                fixed_count += 1
                print()

    if fixed_count > 0:
        # Save the fixed data
        try:
            with posts_file.open("w", encoding="utf-8") as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)
            print(f"✅ Fixed {fixed_count} slugs and saved to posts_data.json")
        except Exception as e:
            print(f"❌ Error saving fixed data: {e}")
    else:
        print("✅ No slugs needed fixing.")


if __name__ == "__main__":
    main()
