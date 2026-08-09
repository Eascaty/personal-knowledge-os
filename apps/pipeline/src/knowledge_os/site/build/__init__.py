"""Static-site normalization and artifact generation."""

from .builder import BuildResult, SiteDataError, build_site, normalize_site_data

__all__ = ["BuildResult", "SiteDataError", "build_site", "normalize_site_data"]
