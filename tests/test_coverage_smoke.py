import contextlib
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@contextlib.contextmanager
def _chdir(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class TestCoverageSmoke(unittest.TestCase):
    """Smoke tests to exercise modules that are otherwise run as scripts.

    These are intentionally light: they exist to keep overall coverage above the
    project threshold without relying on subprocess execution (which coverage
    does not count).
    """

    def test_core_helpers_and_tools_are_exercised(self):
        from devto_mirror.core import constants
        from devto_mirror.core.article_fetcher import fetch_all_articles_from_api
        from devto_mirror.core.path_utils import sanitize_filename, sanitize_slug, validate_safe_path
        from devto_mirror.core.run_state import get_last_run_timestamp, mark_no_new_posts, set_last_run_timestamp
        from devto_mirror.tools.analyze_descriptions import analyze_posts_data
        from devto_mirror.tools.clean_posts import dedupe_posts, key_for
        from devto_mirror.tools.fix_slugs import extract_slug_from_url

        self.assertEqual(constants.POSTS_DATA_FILE, "posts_data.json")
        self.assertEqual(sanitize_filename("a/b:c"), "a-b-c")
        self.assertEqual(sanitize_slug("x" * 200, max_length=10), "x" * 10)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            # validate_safe_path
            base = root / "base"
            base.mkdir()
            safe = validate_safe_path(base, "child.txt")
            self.assertEqual(safe, (base / "child.txt").resolve())
            with self.assertRaises(ValueError):
                validate_safe_path(base, "../escape.txt")

            # run_state helpers
            run_file = root / "last_run.txt"
            self.assertIsNone(get_last_run_timestamp(run_file))
            ts = set_last_run_timestamp(run_file)
            self.assertTrue(ts)
            self.assertEqual(get_last_run_timestamp(run_file), ts)

            marker = root / "no_new_posts.flag"
            gh_output = root / "gh_output.txt"
            gh_summary = root / "gh_summary.md"
            mark_no_new_posts(
                marker_path=marker,
                github_output_path=str(gh_output),
                github_step_summary_path=str(gh_summary),
            )
            self.assertTrue(marker.exists())
            self.assertIn("no_new_posts=true", gh_output.read_text(encoding="utf-8"))
            self.assertIn("No new posts", gh_summary.read_text(encoding="utf-8"))

            # article_fetcher (validation and forced-empty branches; never hits network)
            old_env = os.environ.copy()
            try:
                os.environ["DEVTO_MIRROR_FORCE_EMPTY_FEED"] = "true"
                res = fetch_all_articles_from_api(
                    username="testuser",
                    last_run_iso="2025-01-01T00:00:00+00:00",
                    posts_data_path=root / "posts_data.json",
                    validation_mode=False,
                )
                self.assertTrue(res.success)
                self.assertTrue(res.no_new_posts)
                self.assertEqual(res.articles, [])

                os.environ.pop("DEVTO_MIRROR_FORCE_EMPTY_FEED", None)
                os.environ["VALIDATION_NO_POSTS"] = "true"
                res2 = fetch_all_articles_from_api(
                    username="testuser",
                    last_run_iso=None,
                    posts_data_path=root / "posts_data.json",
                    validation_mode=True,
                )
                self.assertTrue(res2.success)
                self.assertEqual(res2.articles, [])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            # analyze_descriptions
            long_desc = "x" * (constants.SEO_DESCRIPTION_WARNING + 1)
            posts_path = root / "posts_data.json"
            posts_path.write_text(
                json.dumps(
                    [
                        {"title": "A", "description": long_desc, "link": "https://example.com/a"},
                        {"title": "B", "description": "", "link": "https://example.com/b"},
                    ]
                ),
                encoding="utf-8",
            )
            long, missing = analyze_posts_data(str(posts_path))
            self.assertEqual(len(long), 1)
            self.assertEqual(len(missing), 1)

            # clean_posts helpers
            a = {"link": "https://example.com/post/", "date": "2024-01-01T00:00:00Z"}
            b = {"link": "https://example.com/post", "date": "2024-01-02T00:00:00Z"}
            self.assertEqual(key_for(a), "https://example.com/post")
            deduped = dedupe_posts([a, b])
            self.assertEqual(len(deduped), 1)

            # fix_slugs helper
            self.assertEqual(extract_slug_from_url("https://dev.to/me/my-post-123"), "my-post-123")


class TestSiteGenerationModules(unittest.TestCase):
    def test_renderer_main_writes_index_and_sitemap(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "posts_data.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "Hello",
                            "link": "https://dev.to/testuser/hello-1",
                            "date": "2024-01-01T00:00:00Z",
                            "slug": "hello-1",
                            "description": "desc",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            old_env = os.environ.copy()
            try:
                os.environ["GH_USERNAME"] = "testuser"
                os.environ["DEVTO_USERNAME"] = "testuser"
                with _chdir(root):
                    renderer.main()
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertTrue((root / "index.html").exists())
            self.assertTrue((root / "sitemap.xml").exists())

    def test_generator_main_runs_in_validation_mode(self):
        # Importing generator reads env at import-time; set env before import.
        old_env = os.environ.copy()
        try:
            os.environ["VALIDATION_MODE"] = "true"
            os.environ["DEVTO_USERNAME"] = "testuser"
            os.environ["GH_USERNAME"] = "testuser"
            os.environ["FORCE_FULL_REGEN"] = "true"

            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "assets").mkdir()
                (root / "assets" / "devto-mirror.jpg").touch()

                with _chdir(root):
                    # Ensure we get a fresh import that runs in the temp cwd.
                    if "devto_mirror.site_generation.generator" in importlib.sys.modules:
                        importlib.sys.modules.pop("devto_mirror.site_generation.generator")
                    gen = importlib.import_module("devto_mirror.site_generation.generator")
                    gen.main()

                self.assertTrue((root / "index.html").exists())
                self.assertTrue((root / "sitemap.xml").exists())
                self.assertTrue((root / "posts_data.json").exists())
                self.assertTrue((root / "last_run.txt").exists())
                posts_dir = root / "posts"
                self.assertTrue(posts_dir.exists())
                self.assertTrue(list(posts_dir.glob("*.html")))
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_generator_with_site_domain(self):
        old_env = os.environ.copy()
        try:
            os.environ["VALIDATION_MODE"] = "true"
            os.environ["DEVTO_USERNAME"] = "testuser"
            os.environ["SITE_DOMAIN"] = "crawly.checkmarkdevtools.dev"
            os.environ["FORCE_FULL_REGEN"] = "true"

            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "assets").mkdir()
                (root / "assets" / "devto-mirror.jpg").touch()

                with _chdir(root):
                    importlib.sys.modules.pop("devto_mirror.site_generation.generator", None)
                    gen = importlib.import_module("devto_mirror.site_generation.generator")
                    self.assertEqual(gen.HOME, "https://crawly.checkmarkdevtools.dev/")
                    self.assertEqual(gen.ROOT_HOME, "https://crawly.checkmarkdevtools.dev/")
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_generator_fallback_to_gh_username(self):
        old_env = os.environ.copy()
        try:
            os.environ["VALIDATION_MODE"] = "true"
            os.environ["DEVTO_USERNAME"] = "testuser"
            os.environ["GH_USERNAME"] = "testuser"
            os.environ["FORCE_FULL_REGEN"] = "true"
            # Ensure SITE_DOMAIN is unset so generator falls back to GH_USERNAME.
            os.environ.pop("SITE_DOMAIN", None)

            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "assets").mkdir()
                (root / "assets" / "devto-mirror.jpg").touch()

                with _chdir(root):
                    importlib.sys.modules.pop("devto_mirror.site_generation.generator", None)
                    gen = importlib.import_module("devto_mirror.site_generation.generator")
                    self.assertEqual(gen.HOME, "https://testuser.github.io/devto-mirror/")
                    self.assertEqual(gen.ROOT_HOME, "https://testuser.github.io/")
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_generator_short_circuits_on_no_new_posts(self):
        old_env = os.environ.copy()
        try:
            os.environ["VALIDATION_MODE"] = "false"
            os.environ["DEVTO_USERNAME"] = "testuser"
            os.environ["GH_USERNAME"] = "testuser"
            os.environ["FORCE_FULL_REGEN"] = "false"
            os.environ["DEVTO_MIRROR_FORCE_EMPTY_FEED"] = "true"

            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "assets").mkdir()
                (root / "assets" / "devto-mirror.jpg").touch()
                (root / "last_run.txt").write_text("2025-01-01T00:00:00+00:00", encoding="utf-8")

                with _chdir(root):
                    importlib.sys.modules.pop("devto_mirror.site_generation.generator", None)
                    gen = importlib.import_module("devto_mirror.site_generation.generator")
                    with self.assertRaises(SystemExit):
                        gen.main()

                self.assertTrue((root / "no_new_posts.flag").exists())
                self.assertFalse((root / "index.html").exists())
                self.assertFalse((root / "sitemap.xml").exists())
        finally:
            os.environ.clear()
            os.environ.update(old_env)


class TestMoreCoverageTargets(unittest.TestCase):
    def test_article_fetcher_cache_fallback_without_network(self):
        from devto_mirror.core import article_fetcher

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            posts_path = root / "posts_data.json"
            posts_path.write_text(
                json.dumps(
                    [
                        {
                            "id": 1,
                            "title": "Cached",
                            "link": "https://dev.to/testuser/cached-1",
                            "date": "2024-01-01T00:00:00Z",
                            "api_data": {"id": 1, "published_at": "2024-01-01T00:00:00Z"},
                        },
                        "not-a-dict",
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch.object(article_fetcher, "_fetch_article_pages", return_value=[{"id": 1}]),
                patch.object(article_fetcher, "_fetch_full_articles", return_value=([], [{"id": 1}])),
            ):
                res = article_fetcher.fetch_all_articles_from_api(
                    username="testuser",
                    last_run_iso=None,
                    posts_data_path=posts_path,
                    validation_mode=False,
                )

            self.assertFalse(res.success)
            self.assertEqual(res.source, "cache")
            self.assertTrue(res.articles)
            self.assertEqual(res.articles[0]["title"], "Cached")

    def test_renderer_merge_posts_and_comments_paths(self):
        from devto_mirror.site_generation import renderer

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "posts_data.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "Old",
                            "link": "https://dev.to/testuser/old-1",
                            "date": "2024-01-01T00:00:00Z",
                            "slug": "old-1",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (root / "posts_data_new.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "New",
                            "link": "https://dev.to/testuser/new-2",
                            "date": "2024-01-02T00:00:00Z",
                            "slug": "new-2",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (root / "comments.txt").write_text(
                "https://dev.to/testuser/new-2#comment-abc|Nice one\nhttps://dev.to/testuser/new-2#comment-abc|Dup\n",
                encoding="utf-8",
            )

            old_env = os.environ.copy()
            try:
                os.environ["GH_USERNAME"] = "testuser"
                os.environ["DEVTO_USERNAME"] = "testuser"
                with _chdir(root):
                    renderer.main()
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertTrue((root / "index.html").exists())
            self.assertTrue((root / "sitemap.xml").exists())

    def test_analyze_descriptions_generate_report(self):
        from devto_mirror.tools import analyze_descriptions

        long = [
            {
                "title": "T",
                "url": "https://example.com/t",
                "description": "x" * 200,
                "length": 200,
                "status": "EXCEEDS LIMIT",
            }
        ]
        missing = [{"title": "M", "url": "https://example.com/m", "reason": "Empty"}]

        with patch("builtins.print"):
            analyze_descriptions.print_summary(long, missing)
            analyze_descriptions.print_long_descriptions(long)
            analyze_descriptions.print_missing_descriptions(missing)
            analyze_descriptions.print_markdown_comment(long, missing)
            analyze_descriptions.generate_report(long, missing)

    def test_fix_slugs_main_updates_file_in_place(self):
        from devto_mirror.tools import fix_slugs

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            posts = [
                {"title": "A", "link": "https://dev.to/testuser/my-post-123", "slug": "my-post"},
                {"title": "B", "link": "", "slug": "unchanged"},
            ]
            (root / "posts_data.json").write_text(json.dumps(posts), encoding="utf-8")

            with _chdir(root), patch("builtins.print"):
                fix_slugs.main()

            self.assertTrue((root / "posts_data.json.backup").exists())
            updated = json.loads((root / "posts_data.json").read_text(encoding="utf-8"))
            self.assertEqual(updated[0]["slug"], "my-post-123")


class TestGeneratorExtra(unittest.TestCase):
    """Additional tests for site_generation.generator that boost coverage."""

    def _import_generator(self):
        """Import generator with VALIDATION_MODE=true and required env vars set."""
        import importlib

        importlib.sys.modules.pop("devto_mirror.site_generation.generator", None)
        return importlib.import_module("devto_mirror.site_generation.generator")

    def setUp(self):
        self._old_env = os.environ.copy()
        os.environ["VALIDATION_MODE"] = "true"
        os.environ["DEVTO_USERNAME"] = "testuser"
        os.environ["GH_USERNAME"] = "testuser"
        os.environ.pop("SITE_DOMAIN", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_env)

    def test_post_from_api_data_sets_fields(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post(
                    {
                        "title": "Hello World",
                        "url": "https://dev.to/testuser/hello-world-1",
                        "published_at": "2024-01-01T00:00:00Z",
                        "body_html": "<p>Content</p>",
                        "description": "A description",
                        "cover_image": "https://example.com/cover.jpg",
                        "tag_list": ["python", "tutorial"],
                        "slug": "hello-world-1",
                        "user": {"name": "Test User", "username": "testuser"},
                    }
                )
        self.assertEqual(post.title, "Hello World")
        self.assertEqual(post.tags, ["python", "tutorial"])
        self.assertIn("hello-world-1", post.slug)

    def test_post_normalize_tags_list(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post({"title": "T", "url": "https://dev.to/u/t-1", "tag_list": ["a", "b", "c"]})
        self.assertEqual(post.tags, ["a", "b", "c"])

    def test_post_normalize_tags_string_csv(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post({"title": "T", "url": "https://dev.to/u/t-1", "tag_list": "tag1,tag2,tag3"})
        self.assertEqual(post.tags, ["tag1", "tag2", "tag3"])

    def test_post_normalize_tags_string_space_separated(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post({"title": "T", "url": "https://dev.to/u/t-1", "tag_list": "tag1 tag2"})
        self.assertEqual(post.tags, ["tag1", "tag2"])

    def test_post_normalize_tags_single(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post({"title": "T", "url": "https://dev.to/u/t-1", "tag_list": "singletag"})
        self.assertEqual(post.tags, ["singletag"])

    def test_post_normalize_tags_empty(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post({"title": "T", "url": "https://dev.to/u/t-1", "tag_list": []})
        self.assertEqual(post.tags, [])

    def test_post_to_dict_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                api_data = {
                    "title": "Round Trip",
                    "url": "https://dev.to/testuser/round-trip-42",
                    "published_at": "2024-01-01T00:00:00Z",
                    "body_html": "<p>Content</p>",
                    "description": "desc",
                    "cover_image": "",
                    "tag_list": ["test"],
                    "slug": "round-trip-42",
                    "user": {"name": "T User", "username": "testuser"},
                }
                post = gen.Post(api_data)
                d = post.to_dict()
                restored = gen.Post.from_dict(d)
        self.assertEqual(post.title, restored.title)
        self.assertEqual(post.tags, restored.tags)
        self.assertEqual(post.slug, restored.slug)

    def test_strip_html_removes_tags(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                result = gen.strip_html("<p>Hello <strong>world</strong></p>")
        self.assertEqual(result, "Hello world")

    def test_strip_html_empty_input(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                result = gen.strip_html("")
        self.assertEqual(result, "")

    def test_ensure_img_dimensions_adds_attrs_for_plain_img(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                content = '<img src="https://example.com/photo.jpg" alt="Photo">'
                result = gen.ensure_img_dimensions(content)
        self.assertIn("width=", result)
        self.assertIn("height=", result)

    def test_ensure_img_dimensions_skips_existing_attrs(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                content = '<img src="photo.jpg" width="800" height="450" alt="x">'
                result = gen.ensure_img_dimensions(content)
        # Should not add additional width/height
        self.assertEqual(result.count('width="'), 1)
        self.assertEqual(result.count('height="'), 1)

    def test_ensure_img_dimensions_cover_image_uses_banner_size(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                cover_src = "https://example.com/cover.jpg"
                content = f'<img src="{cover_src}" alt="Cover">'
                result = gen.ensure_img_dimensions(content, cover_src=cover_src)
        self.assertIn('width="1000"', result)
        self.assertIn('height="420"', result)

    def test_choose_img_size_for_cover_src(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                w, h = gen._choose_img_size_for_src(
                    src_val="https://example.com/cover.jpg",
                    cover_src="https://example.com/cover.jpg",
                )
        self.assertEqual(w, 1000)
        self.assertEqual(h, 420)

    def test_choose_img_size_for_content_image(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                w, h = gen._choose_img_size_for_src(
                    src_val="https://example.com/photo.jpg",
                    cover_src=None,
                )
        self.assertEqual(w, 800)
        self.assertEqual(h, 450)

    def test_is_first_run_true_when_no_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with _chdir(root):
                gen = self._import_generator()
                result = gen.is_first_run()
        self.assertTrue(result)

    def test_is_first_run_false_when_file_exists(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "posts_data.json").write_text("[]", encoding="utf-8")
            with _chdir(root):
                gen = self._import_generator()
                result = gen.is_first_run()
        self.assertFalse(result)

    def test_should_force_full_regen_env_true(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                with patch.dict(os.environ, {"FORCE_FULL_REGEN": "true"}):
                    result = gen._should_force_full_regen()
        self.assertTrue(result)

    def test_should_force_full_regen_env_false(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                with patch.dict(os.environ, {"FORCE_FULL_REGEN": "false"}):
                    result = gen._should_force_full_regen()
        self.assertFalse(result)

    def test_find_new_posts_filters_by_link(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                existing_posts = [{"link": "https://dev.to/user/existing-1"}]
                api_articles = [
                    {
                        "title": "Existing",
                        "url": "https://dev.to/user/existing-1",
                        "published_at": "2024-01-01T00:00:00Z",
                        "body_html": "",
                        "description": "",
                        "cover_image": "",
                        "tag_list": [],
                        "slug": "existing-1",
                    },
                    {
                        "title": "New Post",
                        "url": "https://dev.to/user/new-post-2",
                        "published_at": "2024-01-02T00:00:00Z",
                        "body_html": "",
                        "description": "",
                        "cover_image": "",
                        "tag_list": [],
                        "slug": "new-post-2",
                    },
                ]
                new_posts = gen.find_new_posts(api_articles, existing_posts)
        self.assertEqual(len(new_posts), 1)
        self.assertEqual(new_posts[0].title, "New Post")

    def test_post_with_no_url_uses_home(self):
        """Post with no url field should use HOME as link."""
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post({"title": "No URL"})
        self.assertEqual(post.link, gen.HOME)

    def test_post_slug_from_url_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                gen = self._import_generator()
                post = gen.Post(
                    {
                        "title": "Slug Test",
                        "url": "https://dev.to/testuser/my-great-post-12345",
                    }
                )
        self.assertEqual(post.slug, "my-great-post-12345")


if __name__ == "__main__":
    unittest.main()
