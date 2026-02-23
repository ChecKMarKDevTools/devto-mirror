"""
Tests for the AIOptimizationManager module.
"""

import unittest
from unittest.mock import Mock, patch

from devto_mirror.ai_optimization import AIOptimizationManager, create_default_ai_optimization_manager


class TestAIOptimizationManager(unittest.TestCase):
    """Test cases for AIOptimizationManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_schema_generator = Mock()
        self.mock_metadata_enhancer = Mock()
        self.mock_content_analyzer = Mock()
        self.mock_cross_reference_manager = Mock()
        self.mock_sitemap_generator = Mock()

        self.manager = AIOptimizationManager(
            schema_generator=self.mock_schema_generator,
            metadata_enhancer=self.mock_metadata_enhancer,
            content_analyzer=self.mock_content_analyzer,
            cross_reference_manager=self.mock_cross_reference_manager,
            sitemap_generator=self.mock_sitemap_generator,
        )

    def test_initialization_with_all_components(self):
        """Test manager initialization with all components."""
        self.assertTrue(self.manager.optimization_enabled)
        self.assertTrue(self.manager.component_status["schema"])
        self.assertTrue(self.manager.component_status["metadata"])
        self.assertTrue(self.manager.component_status["content"])
        self.assertTrue(self.manager.component_status["cross_reference"])
        self.assertTrue(self.manager.component_status["sitemap"])

    def test_initialization_with_no_components(self):
        """Test manager initialization with no components."""
        empty_manager = AIOptimizationManager()

        self.assertTrue(empty_manager.optimization_enabled)
        self.assertFalse(empty_manager.component_status["schema"])
        self.assertFalse(empty_manager.component_status["metadata"])
        self.assertFalse(empty_manager.component_status["content"])
        self.assertFalse(empty_manager.component_status["cross_reference"])
        self.assertFalse(empty_manager.component_status["sitemap"])

    def test_optimize_post_with_all_components(self):
        """Test post optimization with all components working."""
        # Set up mock returns
        self.mock_schema_generator.generate_article_schema.return_value = {"@type": "Article"}
        self.mock_schema_generator.generate_breadcrumb_schema.return_value = {"@type": "BreadcrumbList"}
        self.mock_metadata_enhancer.enhance_post_metadata.return_value = {"description": "test"}
        self.mock_content_analyzer.analyze_post_content.return_value = {"topics": ["test"]}
        self.mock_cross_reference_manager.add_source_attribution.return_value = {"source": "dev.to"}
        self.mock_cross_reference_manager.generate_related_links.return_value = []
        self.mock_cross_reference_manager.create_dev_to_backlinks.return_value = {}

        # Create mock post
        mock_post = Mock()
        mock_post.link = "https://dev.to/test/post"
        mock_post.slug = "test-post"
        mock_post.api_data = {}

        result = self.manager.optimize_post(mock_post)

        self.assertTrue(result["optimization_applied"])
        self.assertEqual(len(result["json_ld_schemas"]), 2)
        self.assertEqual(result["enhanced_metadata"]["description"], "test")
        self.assertEqual(result["content_analysis"]["topics"], ["test"])
        self.assertEqual(result["cross_references"]["source_attribution"]["source"], "dev.to")

    def test_optimize_post_with_disabled_optimization(self):
        """Test post optimization when optimization is disabled."""
        self.manager.optimization_enabled = False

        mock_post = Mock()
        result = self.manager.optimize_post(mock_post)

        self.assertFalse(result["optimization_applied"])
        self.assertEqual(result["json_ld_schemas"], [])
        self.assertEqual(result["enhanced_metadata"], {})

    def test_optimize_post_with_component_failure(self):
        """Test post optimization when a component fails."""
        # Make schema generator raise an exception
        self.mock_schema_generator.generate_article_schema.side_effect = Exception("Schema error")

        # Other components work normally
        self.mock_metadata_enhancer.enhance_post_metadata.return_value = {"description": "test"}

        mock_post = Mock()
        mock_post.link = "https://dev.to/test/post"
        mock_post.slug = "test-post"
        mock_post.api_data = {}

        # Now that schema generation is considered fatal, manager should
        # propagate the exception. Tests should assert the exception is raised.
        with self.assertRaises(Exception) as cm:
            self.manager.optimize_post(mock_post)
        self.assertIn("Schema error", str(cm.exception))

    def test_generate_optimized_sitemap_success(self):
        """Test successful sitemap generation."""
        self.mock_sitemap_generator.generate_main_sitemap.return_value = "<xml>sitemap</xml>"

        posts = [Mock()]
        comments = [{"id": 1}]

        result = self.manager.generate_optimized_sitemap(posts, comments)

        self.assertEqual(result, "<xml>sitemap</xml>")
        self.mock_sitemap_generator.generate_main_sitemap.assert_called_once_with(posts, comments)

    def test_generate_optimized_sitemap_no_generator(self):
        """Test sitemap generation when no generator is available."""
        manager = AIOptimizationManager()  # No sitemap generator

        result = manager.generate_optimized_sitemap([], [])

        self.assertIsNone(result)

    def test_generate_optimized_sitemap_failure(self):
        """Test sitemap generation when generator fails."""
        self.mock_sitemap_generator.generate_main_sitemap.side_effect = Exception("Sitemap error")
        # Sitemap generation is now fatal for optimized path and should
        # propagate exceptions to callers.
        with self.assertRaises(Exception) as cm:
            self.manager.generate_optimized_sitemap([], [])
        self.assertIn("Sitemap error", str(cm.exception))

    @patch("devto_mirror.ai_optimization.AIOptimizedPost")
    def test_create_optimized_post(self, mock_optimized_post_class):
        """Test creating an optimized post wrapper."""
        mock_post = Mock()
        mock_optimized_post = Mock()
        mock_optimized_post_class.from_post.return_value = mock_optimized_post

        result = self.manager.create_optimized_post(mock_post)

        self.assertEqual(result, mock_optimized_post)
        mock_optimized_post_class.from_post.assert_called_once_with(mock_post, self.mock_content_analyzer)

    @patch("devto_mirror.ai_optimization.AIOptimizedPost")
    def test_create_optimized_posts(self, mock_optimized_post_class):
        """Test creating multiple optimized post wrappers."""
        mock_posts = [Mock(), Mock()]
        mock_optimized_posts = [Mock(), Mock()]
        mock_optimized_post_class.from_post.side_effect = mock_optimized_posts

        result = self.manager.create_optimized_posts(mock_posts)

        self.assertEqual(len(result), 2)
        self.assertEqual(result, mock_optimized_posts)

    def test_get_optimization_status(self):
        """Test getting optimization status."""
        status = self.manager.get_optimization_status()

        self.assertTrue(status["enabled"])
        self.assertEqual(status["active_components"], 5)
        self.assertEqual(len(status["components"]), 5)


class TestCreateDefaultAIOptimizationManager(unittest.TestCase):
    """Test cases for create_default_ai_optimization_manager function."""

    @patch("devto_mirror.ai_optimization.DevToAISitemapGenerator")
    @patch("devto_mirror.ai_optimization.DevToContentAnalyzer")
    @patch("devto_mirror.ai_optimization.DevToMetadataEnhancer")
    @patch("devto_mirror.ai_optimization.DevToSchemaGenerator")
    def test_create_default_manager(self, mock_schema, mock_metadata, mock_content, mock_sitemap):
        """Test creating a default manager with all components."""
        mock_schema_instance = Mock()
        mock_metadata_instance = Mock()
        mock_content_instance = Mock()
        mock_sitemap_instance = Mock()

        mock_schema.return_value = mock_schema_instance
        mock_metadata.return_value = mock_metadata_instance
        mock_content.return_value = mock_content_instance
        mock_sitemap.return_value = mock_sitemap_instance

        manager = create_default_ai_optimization_manager("Test Site", "https://test.com")

        self.assertIsInstance(manager, AIOptimizationManager)
        self.assertEqual(manager.schema_generator, mock_schema_instance)
        self.assertEqual(manager.metadata_enhancer, mock_metadata_instance)
        self.assertEqual(manager.content_analyzer, mock_content_instance)
        self.assertEqual(manager.sitemap_generator, mock_sitemap_instance)
        self.assertIsNone(manager.cross_reference_manager)  # Not implemented yet

        # Verify components were initialized with correct parameters
        mock_schema.assert_called_once_with("Test Site", "https://test.com")
        mock_metadata.assert_called_once_with("Test Site", "https://test.com")
        mock_content.assert_called_once()
        mock_sitemap.assert_called_once_with("Test Site", "https://test.com")


if __name__ == "__main__":
    unittest.main()
