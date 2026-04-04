from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aiopath import AsyncPath


@dataclass
class SortStats:
    """Runtime counters for sorting operations."""

    scanned: int = 0
    copied: int = 0
    renamed: int = 0
    skipped_duplicates: int = 0
    duplicates_detected: int = 0
    duplicates_merged: int = 0
    failed: int = 0
    source_deleted: int = 0
    source_delete_failed: int = 0
    source_dirs_deleted: int = 0
    source_dir_delete_failed: int = 0
    processed_bytes: int = 0
    copied_bytes: int = 0
    deduplicated_bytes: int = 0
    source_deleted_bytes: int = 0
    output_size_bytes: int = 0
    copied_by_extension: dict[str, int] = field(default_factory=dict)
    copied_bytes_by_extension: dict[str, int] = field(default_factory=dict)


class CopyStatus(str, Enum):
    """Supported destination decision statuses for one source file."""

    DIRECT = "direct"
    RENAMED = "renamed"
    DUPLICATE = "duplicate"


class SourceDeleteStatus(str, Enum):
    """Result status for source-file removal in move mode."""

    DELETED = "deleted"
    ALREADY_MISSING = "already_missing"
    FAILED = "failed"


@dataclass(frozen=True)
class CopyDecision:
    """Destination decision for one source file."""

    destination: AsyncPath | None
    status: CopyStatus


@dataclass(frozen=True)
class SourceDeleteResult:
    """Outcome of attempting to remove one source file."""

    status: SourceDeleteStatus
    error: Exception | None = None


@dataclass(frozen=True)
class DirectoryCleanupResult:
    """Summary of empty-directory cleanup operation."""

    deleted_count: int
    failed_count: int
