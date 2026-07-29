"""Static knowledge-site generation.

The module intentionally depends only on the Python standard library.  The
generated site also uses plain HTML, CSS and JavaScript, so it can be hosted by
any static-file service.
"""

from .builder import BuildResult, SiteDataError, build_site, normalize_site_data

__all__ = [
    "BuildResult",
    "SiteDataError",
    "build_site",
    "normalize_site_data",
]
