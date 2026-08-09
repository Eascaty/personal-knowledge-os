"""Backward-compatible facade for split knowledge processing modules."""

from .artifacts import build_site_data, rebuild_vault_indexes
from .classification import Classification, classify_document
from .extraction import ExtractionError, NeedsExternalTool, extract_source
from .runner import RunSummary, process_jobs

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
