"""Compatibility facade for knowledge processing use cases."""

from .processing.service import (
    Classification,
    ExtractionError,
    NeedsExternalTool,
    RunSummary,
    build_site_data,
    classify_document,
    extract_source,
    process_jobs,
    rebuild_vault_indexes,
)

__all__ = [
    "Classification",
    "ExtractionError",
    "NeedsExternalTool",
    "RunSummary",
    "build_site_data",
    "classify_document",
    "extract_source",
    "process_jobs",
    "rebuild_vault_indexes",
]
