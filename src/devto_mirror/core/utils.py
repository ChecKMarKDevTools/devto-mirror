"""
Shared utilities for devto-mirror scripts
"""

import pathlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Use a Jinja environment with autoescape enabled for HTML/XML templates
# Also add FileSystemLoader to load templates from files
template_dir = pathlib.Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(template_dir) if template_dir.exists() else None,
    autoescape=select_autoescape(["html", "xml"]),
)


# Load post template from file if available, otherwise use inline template
def get_post_template():
    """Get the post template, preferring file-based template if available"""
    try:
        if template_dir.exists():
            return env.get_template("post_template.html")
    except Exception as e:
        # Log the error but continue with fallback
        import logging

        logging.debug(f"Failed to load post template from file: {e}")

    # Fallback to inline template
    return env.from_string(POST_TEMPLATE_INLINE)


# Inline post template as fallback
POST_TEMPLATE_INLINE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<title>{{ title }}</title>
<link rel="canonical" href="{{ canonical }}">
<meta name="description" content="{{ description }}">
<meta name="viewport" content="width=device-width, initial-scale=1">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="article">
<meta property="og:url" content="{{ canonical }}">
<meta property="og:title" content="{{ title }}">
<meta property="og:description" content="{{ description }}">
<meta property="og:image" content="{{ social_image }}">
<meta property="og:site_name" content="{{ site_name }}">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:url" content="{{ canonical }}">
<meta name="twitter:title" content="{{ title }}">
<meta name="twitter:description" content="{{ description }}">
<meta name="twitter:image" content="{{ social_image }}">

<!-- LinkedIn -->
<meta property="linkedin:title" content="{{ title }}">
<meta property="linkedin:description" content="{{ description }}">
<meta property="linkedin:image" content="{{ social_image }}">

<!-- Additional Social Meta -->
<meta name="image" content="{{ social_image }}">
<meta name="author" content="{{ author }}">
{% if tags %}<meta name="keywords" content="{{ tags|join(', ') }}">{% endif %}

<!-- AI-Specific Enhanced Metadata -->
{% if enhanced_metadata %}
{% for name, content in enhanced_metadata.items() %}
<meta name="{{ name }}" content="{{ content }}">
{% endfor %}
{% endif %}

<!-- Cross-Reference Attribution Meta Tags -->
{% if cross_references and cross_references.attribution and cross_references.attribution.meta_tags %}
{% for name, content in cross_references.attribution.meta_tags.items() %}
<meta name="{{ name }}" content="{{ content }}">
{% endfor %}
{% endif %}

<!-- JSON-LD Structured Data -->
{% if json_ld_schemas %}
{% for schema in json_ld_schemas %}
<script type="application/ld+json">
{{ schema | tojson }}
</script>
{% endfor %}
{% endif %}
</head><body>
<main>
  <h1><a href="{{ canonical }}">{{ title }}</a></h1>
  {% if cover_image %}
  <img src="{{ cover_image }}?v=2"
      width="1000" height="420"
      alt="Banner image for {{ title }}"
      loading="lazy"
      style="width:100%;max-width:1000px;height:auto;margin:1em 0;aspect-ratio:1000/420;">
  {% endif %}
  {% if date %}<p><em>Published: {{ date }}</em></p>{% endif %}
    {% if tags %}
    <p><strong>Tags:</strong>
        {% for tag in tags %}
            <span style="background:#e9ecef; padding:2px 6px; margin:2px;
                         border-radius:3px; font-size:0.9em; color:#495057;">
                #{{ tag }}
            </span>{% if not loop.last %} {% endif %}
        {% endfor %}
    </p>
    {% endif %}
  {% if description %}<p><em>{{ description }}</em></p>{% endif %}

  <!-- Enhanced Dev.to Attribution -->
  {% if cross_references and cross_references.attribution and cross_references.has_attribution %}
  {{ cross_references.attribution.attribution_html | safe }}
  {% endif %}

  <article>{{ content }}</article>

  <!-- Dev.to Backlinks -->
  {% if cross_references and cross_references.backlinks and cross_references.has_backlinks %}
  {{ cross_references.backlinks.backlink_html | safe }}
  {% endif %}

  <!-- Related Posts Section -->
  {% if cross_references and cross_references.related_posts and cross_references.has_related_posts %}
  <section style="margin: 30px 0; padding: 20px; background-color: #f8f9fa; border-radius: 8px;
                  border: 1px solid #e9ecef;">
    <h3 style="margin-top: 0; color: #495057; font-size: 1.2em;">📚 Related Articles</h3>
    <ul style="list-style: none; padding: 0; margin: 0;">
      {% for related in cross_references.related_posts %}
      <li style="margin: 10px 0; padding: 10px; background-color: white; border-radius: 5px;
                 border-left: 3px solid #003f8a;">
        <div>
          <a href="{{ related.local_link }}" style="color: #003f8a; text-decoration: none; font-weight: bold;">
            {{ related.title }}
          </a>
          {% if related.description %}
          <p style="margin: 5px 0; color: #495057; font-size: 0.9em;">{{ related.description }}</p>
          {% endif %}
          {% if related.shared_tags %}
          <div style="margin: 5px 0;">
            <small style="color: #495057;">Shared tags:
              {% for tag in related.shared_tags %}
                <span style="background: #e9ecef; padding: 1px 4px; border-radius: 2px;
                             margin: 0 2px; color:#495057;">#{{ tag }}</span>
              {% endfor %}
            </small>
          </div>
          {% endif %}
        </div>
      </li>
      {% endfor %}
    </ul>
  </section>
  {% endif %}

  <p><a href="{{ canonical }}">Read on Dev.to →</a></p>
</main>
</body></html>"""

# Shared templates
INDEX_TMPL = env.from_string("""<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<title>{{ username }}—Dev.to Mirror</title>
<link rel="canonical" href="{{ canonical }}">
<meta name="description" content="{{ site_description }}">
<meta name="viewport" content="width=device-width, initial-scale=1">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="website">
<meta property="og:url" content="{{ home }}">
<meta property="og:title" content="{{ username }}—Dev.to Mirror">
<meta property="og:description" content="{{ site_description }}">
<meta property="og:image" content="{{ social_image }}">
<meta property="og:site_name" content="{{ username }}—Dev.to Mirror">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:url" content="{{ home }}">
<meta name="twitter:title" content="{{ username }}—Dev.to Mirror">
<meta name="twitter:description" content="{{ site_description }}">
<meta name="twitter:image" content="{{ social_image }}">

<!-- LinkedIn -->
<meta property="linkedin:title" content="{{ username }}—Dev.to Mirror">
<meta property="linkedin:description" content="{{ site_description }}">
<meta property="linkedin:image" content="{{ social_image }}">

<!-- Additional Social Meta -->
<meta name="image" content="{{ social_image }}">
<meta name="author" content="{{ username }}">
</head><body>
<main>
  <h1>{{ username }}—Dev.to Mirror</h1>
  <ul>
  {% for p in posts %}
        <li>
            <a href="posts/{{ p.slug }}.html">{{ p.title }}</a>
            {% if p.description %}—{{ p.description }}{% endif %}
                        {% if p.tags %}
                               —<small>Tags:
                                    {% for tag in p.tags %}
                                        #{{ tag }}{% if not loop.last %}, {% endif %}
                                    {% endfor %}
                                </small>
                        {% endif %}
           —<small>{{ p.date }}</small>
        </li>
  {% endfor %}
  </ul>
  {% if comments %}<h2>Comment Notes</h2>
  <ul>
  {% for c in comments %}
    <li><a href="{{ c.local }}">{{ c.text }}</a></li>
  {% endfor %}
  </ul>{% endif %}
  <p>Canonical lives on Dev.to. This is just a crawler-friendly mirror.</p>
</main>
</body></html>
""")

SITEMAP_TMPL = env.from_string("""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{{ home }}</loc></url>
  {% for p in posts %}
    <url><loc>{{ home }}posts/{{ p.slug }}.html</loc></url>
  {% endfor %}
  {% for c in comments %}
    <url><loc>{{ home }}{{ c.local }}</loc></url>
  {% endfor %}
</urlset>
""")


def _parse_iso_date_str(s: str) -> datetime:
    """Parse an ISO date string, handling the 'Z' suffix."""
    if s.endswith("Z"):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    return datetime.fromisoformat(s)


def parse_date(date_str):
    """
    Unified date parsing function that handles various formats.
    Returns timezone-aware datetime when possible, otherwise None.
    """
    if not date_str:
        return None

    if isinstance(date_str, datetime):
        dt = date_str
        # Normalize naive datetimes to UTC to avoid comparison errors
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    if isinstance(date_str, (int, float)):
        try:
            dt = datetime.fromtimestamp(date_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    s = str(date_str).strip()

    # Try different parsing formats in order
    formats_to_try = [
        # ISO format with Z
        _parse_iso_date_str,
        # RFC-style parse
        parsedate_to_datetime,
        # Basic ISO without timezone
        lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S"),
    ]

    for parse_func in formats_to_try:
        try:
            dt = parse_func(s)
            if dt and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError, OverflowError):
            continue  # Try next format

    return None


def _post_identity_key(post_dict: dict) -> str | None:
    """Return a stable identity key for a post dict (id-based or link-based)."""
    api_data = post_dict.get("api_data") if isinstance(post_dict.get("api_data"), dict) else {}
    try:
        post_id = int(post_dict.get("id") or api_data.get("id") or 0)
    except (TypeError, ValueError):
        post_id = 0
    if post_id:
        return f"id:{post_id}"

    link = (post_dict.get("link") or "").strip()
    if link.endswith("/"):
        link = link[:-1]
    if link:
        return f"link:{link}"
    return None


def _post_activity_dt(post_dict: dict) -> datetime | None:
    """Return the most recent activity datetime for a post dict."""
    api_data = post_dict.get("api_data") if isinstance(post_dict.get("api_data"), dict) else {}
    candidates = [
        api_data.get("edited_at"),
        api_data.get("updated_at"),
        post_dict.get("edited_at"),
        post_dict.get("updated_at"),
        api_data.get("published_at"),
        post_dict.get("published_at"),
        post_dict.get("date"),
    ]
    dts = [dt for dt in (parse_date(v) for v in candidates) if dt is not None]
    return max(dts) if dts else None


def _merge_post_dicts(*, primary: dict, secondary: dict) -> dict:
    """Merge missing fields from secondary into primary (primary wins)."""
    merged = dict(primary)
    for field in (
        "title",
        "link",
        "date",
        "content_html",
        "description",
        "slug",
        "cover_image",
        "tags",
        "author",
        "id",
    ):
        if not merged.get(field) and secondary.get(field):
            merged[field] = secondary[field]

    # Merge api_data shallowly; primary wins on conflicts.
    primary_api = primary.get("api_data") if isinstance(primary.get("api_data"), dict) else {}
    secondary_api = secondary.get("api_data") if isinstance(secondary.get("api_data"), dict) else {}
    merged_api = dict(secondary_api)
    merged_api.update(primary_api)
    merged["api_data"] = merged_api
    return merged


def _post_date_sort_key(p: dict) -> datetime:
    """Sort key for posts: most recent activity first, with UTC fallback."""
    fallback = datetime.min.replace(tzinfo=timezone.utc)
    return _post_activity_dt(p) or fallback


def dedupe_posts_by_link(posts_list):
    """
    Remove duplicate posts based on stable identity.

    Identity rules:
    - Prefer Dev.to article id (from top-level "id" or "api_data.id")
    - Fall back to canonical link (top-level "link")

    When duplicates are found, keep the post with the most recent *activity*
    timestamp (edited/updated/published). This ensures delta runs can update
    existing mirrored posts.

    Returns a list of posts sorted by the same activity timestamp (newest first).
    """
    if not posts_list:
        return []

    posts_map = {}

    for post in posts_list:
        post_dict = post.to_dict() if hasattr(post, "to_dict") else post
        if not isinstance(post_dict, dict):
            continue

        key = _post_identity_key(post_dict)
        if not key:
            continue

        incoming_dt = _post_activity_dt(post_dict)

        existing = posts_map.get(key)
        if existing is None:
            posts_map[key] = post_dict
            continue

        existing_dt = _post_activity_dt(existing)
        if incoming_dt and (not existing_dt or incoming_dt > existing_dt):
            # Incoming is newer: keep it, but don't drop missing fields.
            posts_map[key] = _merge_post_dicts(primary=post_dict, secondary=existing)
        else:
            # Existing stays, but it may be missing fields that incoming has.
            posts_map[key] = _merge_post_dicts(primary=existing, secondary=post_dict)

    deduped = sorted(posts_map.values(), key=_post_date_sort_key, reverse=True)
    return deduped
