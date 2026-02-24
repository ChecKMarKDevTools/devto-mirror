"""
Top-level package for devto-mirror application.

This module provides access to AI optimization functionality.
The package is organized with application code in the `src/` directory
following standard Python packaging conventions.
"""

__version__ = "1.0.1"
__author__ = "Ashley Childress"

# Make ai_optimization available at package level
try:
    from . import ai_optimization

    __all__ = ["ai_optimization"]
except ImportError:
    ai_optimization = None
    __all__ = []
