from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiopath import AsyncPath

from sorter.models import CopyStatus, SortStats, SourceDeleteStatus
from sorter.protocols import (
    CollisionResolver,
    EmptyDirectoryCleaner,
    ExtensionResolver,
    FileCopier,
    SourceFileRemover,
)

LOGGER = logging.getLogger(__name__)


class AsyncFileSorter:
    """Coordinates asynchronous folder reading and file copying."""

    def __init__(
        self,
        source_dir: AsyncPath,
        output_dir: AsyncPath,
        workers: int,
        allowed_extensions: set[str] | None,
        excluded_extensions: set[str],
        move_files: bool,
        cleanup_empty_dirs: bool,
        extension_resolver: ExtensionResolver,
        collision_resolver: CollisionResolver,
        file_copier: FileCopier,
        source_file_remover: SourceFileRemover,
        empty_directory_cleaner: EmptyDirectoryCleaner,
    ) -> None:
        self._source_dir = source_dir
        self._output_dir = output_dir
        self._output_root = Path(str(output_dir)).resolve()
        self._allowed_extensions = allowed_extensions
        self._excluded_extensions = excluded_extensions
        self._move_files = move_files
        self._cleanup_empty_dirs = cleanup_empty_dirs
        self._extension_resolver = extension_resolver
        self._collision_resolver = collision_resolver
        self._file_copier = file_copier
        self._source_file_remover = source_file_remover
        self._empty_directory_cleaner = empty_directory_cleaner
        self._worker_count = max(workers, 1)
        self._max_pending_tasks = self._worker_count * 4
        self._semaphore = asyncio.Semaphore(self._worker_count)
        self._stats = SortStats()
        self._stats_lock = asyncio.Lock()
        self._extension_locks: dict[str, asyncio.Lock] = {}

    async def run(self) -> SortStats:
        """Run full asynchronous sorting and return summary stats."""
        tasks: set[asyncio.Task[None]] = set()
        await self._read_folder(self._source_dir, tasks)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=False)

        if self._move_files and self._cleanup_empty_dirs:
            cleanup_result = await self._empty_directory_cleaner.cleanup(
                self._source_dir
            )
            if cleanup_result.deleted_count:
                await self._update_counter(
                    "source_dirs_deleted", cleanup_result.deleted_count
                )
                LOGGER.info(
                    "Removed empty source directories: %d",
                    cleanup_result.deleted_count,
                )

            if cleanup_result.failed_count:
                await self._update_counter(
                    "source_dir_delete_failed",
                    cleanup_result.failed_count,
                )
                await self._update_counter("failed", cleanup_result.failed_count)
                LOGGER.warning(
                    "Failed to remove some empty source directories: %d",
                    cleanup_result.failed_count,
                )

        output_size = await self._calculate_directory_size(Path(str(self._output_dir)))
        await self._set_counter("output_size_bytes", output_size)

        return self._stats

    async def _read_folder(
        self,
        source_dir: AsyncPath,
        tasks: set[asyncio.Task[None]],
    ) -> None:
        """Scan source folder iteratively and schedule bounded copy tasks."""
        directories: list[AsyncPath] = [source_dir]

        while directories:
            current_dir = directories.pop()

            try:
                entries = await asyncio.to_thread(
                    lambda: list(Path(str(current_dir)).iterdir())
                )
            except (OSError, PermissionError) as error:
                await self._update_counter("failed")
                LOGGER.exception("Failed to read folder %s: %s", current_dir, error)
                continue

            for entry in entries:
                if self._is_inside_output(entry):
                    continue

                entry_async = AsyncPath(entry)

                if entry.is_dir():
                    directories.append(entry_async)
                    continue

                if not entry.is_file():
                    continue

                extension = self._extension_resolver.resolve_folder(entry_async)
                if extension in self._excluded_extensions:
                    continue

                if (
                    self._allowed_extensions is not None
                    and extension not in self._allowed_extensions
                ):
                    continue

                file_size = await self._safe_file_size(entry)

                await self._update_counter("scanned")
                if file_size is not None:
                    await self._update_counter("processed_bytes", file_size)

                task = asyncio.create_task(
                    self._copy_file(entry_async, extension, file_size)
                )
                tasks.add(task)

                if len(tasks) >= self._max_pending_tasks:
                    await self._drain_one_completed_task(tasks)

    async def _drain_one_completed_task(self, tasks: set[asyncio.Task[None]]) -> None:
        """Keep number of in-flight tasks bounded to reduce peak memory usage."""
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        tasks.clear()
        tasks.update(pending)

        for completed in done:
            completed.result()

    async def _copy_file(
        self,
        source_file: AsyncPath,
        extension: str,
        file_size: int | None,
    ) -> None:
        """Copy one file into extension-based destination folder."""
        async with self._semaphore:
            target_dir = self._output_dir / extension
            lock = self._extension_locks.setdefault(extension, asyncio.Lock())

            try:
                await target_dir.mkdir(parents=True, exist_ok=True)

                async with lock:
                    decision = await self._collision_resolver.resolve_destination(
                        source_file,
                        target_dir,
                    )

                    if decision.status == CopyStatus.DUPLICATE:
                        await self._update_counter("skipped_duplicates")
                        await self._update_counter("duplicates_detected")
                        await self._update_counter("duplicates_merged")
                        if file_size is not None:
                            await self._update_counter("deduplicated_bytes", file_size)
                        await self._remove_source_file_if_enabled(
                            source_file, file_size
                        )
                        LOGGER.info("Skipped duplicate file: %s", source_file)
                        return

                    if decision.destination is None:
                        await self._update_counter("failed")
                        LOGGER.error(
                            "Internal destination resolution error for %s",
                            source_file,
                        )
                        return

                    await self._file_copier.copy(source_file, decision.destination)

                await self._update_counter("copied")
                if decision.status == CopyStatus.RENAMED:
                    await self._update_counter("renamed")

                if file_size is not None:
                    await self._update_counter("copied_bytes", file_size)
                    await self._update_extension_counter(
                        "copied_bytes_by_extension",
                        extension,
                        file_size,
                    )
                await self._update_extension_counter(
                    "copied_by_extension", extension, 1
                )

                LOGGER.info("Copied %s -> %s", source_file, decision.destination)
                await self._remove_source_file_if_enabled(source_file, file_size)

            except (OSError, PermissionError) as error:
                await self._update_counter("failed")
                if isinstance(error, OSError) and error.errno == 22:
                    LOGGER.error(
                        "Failed to copy %s: %s. Possible cloud-only file; make it "
                        "available offline and retry.",
                        source_file,
                        error,
                    )
                else:
                    LOGGER.exception("Failed to copy %s: %s", source_file, error)

    async def _remove_source_file_if_enabled(
        self,
        source_file: AsyncPath,
        file_size: int | None,
    ) -> None:
        """Remove source file via delegated remover when move mode is enabled."""
        if not self._move_files:
            return

        delete_result = await self._source_file_remover.remove(source_file)

        if delete_result.status == SourceDeleteStatus.DELETED:
            await self._update_counter("source_deleted")
            if file_size is not None:
                await self._update_counter("source_deleted_bytes", file_size)
            LOGGER.info("Removed source file: %s", source_file)
            return

        if delete_result.status == SourceDeleteStatus.ALREADY_MISSING:
            await self._update_counter("source_deleted")
            if file_size is not None:
                await self._update_counter("source_deleted_bytes", file_size)
            LOGGER.warning("Source file already removed: %s", source_file)
            return

        if delete_result.status == SourceDeleteStatus.FAILED:
            await self._update_counter("source_delete_failed")
            await self._update_counter("failed")
            LOGGER.error(
                "Copied/merged but failed to remove source file %s: %s",
                source_file,
                delete_result.error,
            )

    async def _update_counter(self, field_name: str, increment: int = 1) -> None:
        """Safely increment stats counters."""
        async with self._stats_lock:
            current_value = getattr(self._stats, field_name)
            setattr(self._stats, field_name, current_value + increment)

    async def _set_counter(self, field_name: str, value: int) -> None:
        """Safely assign stats counters."""
        async with self._stats_lock:
            setattr(self._stats, field_name, value)

    async def _update_extension_counter(
        self,
        field_name: str,
        extension: str,
        increment: int,
    ) -> None:
        """Safely increment a per-extension stats mapping."""
        async with self._stats_lock:
            extension_stats = getattr(self._stats, field_name)
            extension_stats[extension] = extension_stats.get(extension, 0) + increment

    async def _safe_file_size(self, file_path: Path) -> int | None:
        """Read file size with graceful handling for inaccessible cloud files."""

        def _get_size() -> int:
            return file_path.stat().st_size

        try:
            return await asyncio.to_thread(_get_size)
        except OSError as error:
            LOGGER.warning("Failed to read file size for %s: %s", file_path, error)
            return None

    async def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of all files in a directory recursively."""

        def _sum_size() -> int:
            total = 0
            if not directory.exists():
                return total

            for item in directory.rglob("*"):
                if not item.is_file():
                    continue
                try:
                    total += item.stat().st_size
                except OSError as error:
                    LOGGER.warning(
                        "Failed to read output file size for %s: %s",
                        item,
                        error,
                    )
                    continue
            return total

        return await asyncio.to_thread(_sum_size)

    def _is_inside_output(self, path: Path) -> bool:
        """Protect from recursive self-processing when output is inside source."""
        try:
            path.resolve().relative_to(self._output_root)
            return True
        except ValueError:
            return False
