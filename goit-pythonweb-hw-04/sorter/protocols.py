from __future__ import annotations

from typing import Protocol

from aiopath import AsyncPath

from sorter.models import CopyDecision, DirectoryCleanupResult, SourceDeleteResult


class ExtensionResolver(Protocol):
    """Abstraction for mapping a file into an output subfolder."""

    def resolve_folder(self, source_file: AsyncPath) -> str:
        """Return output folder name for the given source file."""
        ...


class FileHasher(Protocol):
    """Abstraction for hashing file content."""

    async def hash(self, file_path: AsyncPath) -> str:
        """Return deterministic hash for file contents."""
        ...


class CollisionResolver(Protocol):
    """Abstraction for collision and duplicate handling."""

    async def resolve_destination(
        self,
        source_file: AsyncPath,
        target_dir: AsyncPath,
    ) -> CopyDecision:
        """Resolve destination path and return a typed copy-status decision."""
        ...


class FileCopier(Protocol):
    """Abstraction for copying files."""

    async def copy(self, source_file: AsyncPath, destination: AsyncPath) -> None:
        """Copy source file to destination path."""
        ...


class SourceFileRemover(Protocol):
    """Abstraction for source-file removal in move mode."""

    async def remove(self, source_file: AsyncPath) -> SourceDeleteResult:
        """Attempt to remove one source file and return operation result."""
        ...


class EmptyDirectoryCleaner(Protocol):
    """Abstraction for removing empty directories from source tree."""

    async def cleanup(self, source_root: AsyncPath) -> DirectoryCleanupResult:
        """Remove empty dirs under source root and return cleanup summary."""
        ...
