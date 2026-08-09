"""Persistence, queue, taxonomy and search adapters."""

from .sqlite import (
    SCHEMA_VERSION,
    connect,
    initialize_database,
    query_documents,
    status_summary,
    sync_taxonomy,
)

__all__ = [
    "SCHEMA_VERSION",
    "connect",
    "initialize_database",
    "query_documents",
    "status_summary",
    "sync_taxonomy",
]
