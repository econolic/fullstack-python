from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiopath import AsyncPath

from sorter.models import DirectoryCleanupResult, SourceDeleteResult, SourceDeleteStatus

LOGGER = logging.getLogger(__name__)


class LocalSourceFileRemover:
    """Remove source files from filesystem when move mode is enabled."""

    async def remove(self, source_file: AsyncPath) -> SourceDeleteResult:
        source_path = Path(str(source_file))

        try:
            await asyncio.to_thread(source_path.unlink)
            return SourceDeleteResult(status=SourceDeleteStatus.DELETED)
        except FileNotFoundError:
            return SourceDeleteResult(status=SourceDeleteStatus.ALREADY_MISSING)
        except (OSError, PermissionError) as error:
            return SourceDeleteResult(
                status=SourceDeleteStatus.FAILED,
                error=error,
            )


class LocalEmptyDirectoryCleaner:
    """Delete empty directories under source root while skipping output subtree."""

    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root.resolve()

    async def cleanup(self, source_root: AsyncPath) -> DirectoryCleanupResult:
        source_root_path = Path(str(source_root)).resolve()

        def _cleanup_sync() -> DirectoryCleanupResult:
            deleted = 0
            failed = 0

            try:
                directories = [
                    item
                    for item in source_root_path.rglob("*")
                    if item.is_dir() and item != source_root_path
                ]
            except (OSError, PermissionError) as error:
                LOGGER.warning(
                    "Failed to scan source directories for cleanup %s: %s",
                    source_root_path,
                    error,
                )
                return DirectoryCleanupResult(deleted_count=0, failed_count=1)

            directories.sort(key=lambda directory: len(directory.parts), reverse=True)

            for directory in directories:
                if self._is_inside_output(directory):
                    continue

                try:
                    if any(directory.iterdir()):
                        continue
                    directory.rmdir()
                    deleted += 1
                except (OSError, PermissionError) as error:
                    LOGGER.warning(
                        "Failed to remove empty directory %s: %s",
                        directory,
                        error,
                    )
                    failed += 1

            return DirectoryCleanupResult(
                deleted_count=deleted,
                failed_count=failed,
            )

        return await asyncio.to_thread(_cleanup_sync)

    def _is_inside_output(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._output_root)
            return True
        except ValueError:
            return False
