"""Compatibility facade for the static-site build implementation."""

from .build.builder import (
    BuildResult,
    SiteDataError,
    build_site,
    normalize_site_data,
)

__all__ = ["BuildResult", "SiteDataError", "build_site", "normalize_site_data"]
