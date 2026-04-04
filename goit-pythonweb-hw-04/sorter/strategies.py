from __future__ import annotations

import asyncio
import errno
import hashlib
import logging
from pathlib import Path

from aiopath import AsyncPath
from aioshutil import copyfile

from sorter.models import CopyDecision, CopyStatus
from sorter.protocols import FileHasher

LOGGER = logging.getLogger(__name__)


class SuffixExtensionResolver:
    """Default folder strategy based on lowercased file suffix."""

    def resolve_folder(self, source_file: AsyncPath) -> str:
        suffix = Path(str(source_file)).suffix.lower().lstrip(".")
        return suffix if suffix else "no_extension"


def _hash_file_sync(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate SHA-256 hash of a file in chunks."""
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handler:
        for chunk in iter(lambda: file_handler.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Sha256FileHasher:
    """Default hasher implementation using SHA-256."""

    async def hash(self, file_path: AsyncPath) -> str:
        return await asyncio.to_thread(_hash_file_sync, Path(str(file_path)))


class HashCollisionResolver:
    """Collision resolver that deduplicates files by hash inside type folder."""

    def __init__(self, hasher: FileHasher) -> None:
        self._hasher = hasher
        self._hash_index_by_dir: dict[Path, dict[str, AsyncPath]] = {}
        self._indexed_dirs: set[Path] = set()

    async def resolve_destination(
        self,
        source_file: AsyncPath,
        target_dir: AsyncPath,
    ) -> CopyDecision:
        source_name = Path(str(source_file)).name
        destination = target_dir / source_name
        target_dir_path = Path(str(target_dir)).resolve()

        try:
            source_hash = await self._hasher.hash(source_file)
        except OSError as error:
            if error.errno == errno.EINVAL:
                if not await destination.exists():
                    return CopyDecision(
                        destination=destination, status=CopyStatus.DIRECT
                    )
                fallback = await self._next_available_name(target_dir, source_name)
                return CopyDecision(destination=fallback, status=CopyStatus.RENAMED)
            raise

        hash_index = await self._get_hash_index(target_dir_path)
        duplicate = await self._find_duplicate_by_hash(hash_index, source_hash)
        if duplicate is not None:
            return CopyDecision(destination=None, status=CopyStatus.DUPLICATE)

        if not await destination.exists():
            hash_index[source_hash] = destination
            return CopyDecision(destination=destination, status=CopyStatus.DIRECT)

        source_stem = Path(source_name).stem
        source_suffix = Path(source_name).suffix
        index = 1

        while True:
            candidate = target_dir / f"{source_stem}_{index}{source_suffix}"

            if not await candidate.exists():
                hash_index[source_hash] = candidate
                return CopyDecision(destination=candidate, status=CopyStatus.RENAMED)

            index += 1

    async def _get_hash_index(self, target_dir_path: Path) -> dict[str, AsyncPath]:
        """Build hash index once per target folder and reuse it for future checks."""
        hash_index = self._hash_index_by_dir.setdefault(target_dir_path, {})

        if target_dir_path in self._indexed_dirs:
            return hash_index

        if not target_dir_path.exists():
            self._indexed_dirs.add(target_dir_path)
            return hash_index

        entries = await asyncio.to_thread(lambda: list(target_dir_path.iterdir()))
        for entry in entries:
            if not entry.is_file():
                continue

            try:
                entry_hash = await self._hasher.hash(AsyncPath(entry))
            except OSError as error:
                LOGGER.warning(
                    "Failed to hash existing file %s during index build: %s",
                    entry,
                    error,
                )
                continue

            hash_index[entry_hash] = AsyncPath(entry)

        self._indexed_dirs.add(target_dir_path)
        return hash_index

    async def _find_duplicate_by_hash(
        self,
        hash_index: dict[str, AsyncPath],
        source_hash: str,
    ) -> AsyncPath | None:
        """Lookup duplicate by hash with stale-entry cleanup for failed copies."""
        duplicate = hash_index.get(source_hash)
        if duplicate is None:
            return None

        if await duplicate.exists():
            return duplicate

        hash_index.pop(source_hash, None)

        return None

    async def _next_available_name(
        self,
        target_dir: AsyncPath,
        source_name: str,
    ) -> AsyncPath:
        """Find first free destination name with incremental numeric suffix."""
        source_stem = Path(source_name).stem
        source_suffix = Path(source_name).suffix
        index = 1

        while True:
            candidate = target_dir / f"{source_stem}_{index}{source_suffix}"
            if not await candidate.exists():
                return candidate
            index += 1


class HashNameCollisionResolver:
    """Collision resolver that names destination files by content hash."""

    def __init__(self, hasher: FileHasher) -> None:
        self._hasher = hasher

    async def resolve_destination(
        self,
        source_file: AsyncPath,
        target_dir: AsyncPath,
    ) -> CopyDecision:
        source_path = Path(str(source_file))
        suffix = source_path.suffix.lower()

        try:
            source_hash = await self._hasher.hash(source_file)
        except OSError as error:
            if error.errno == errno.EINVAL:
                fallback = await self._next_available_name(target_dir, source_path.name)
                return CopyDecision(destination=fallback, status=CopyStatus.RENAMED)
            raise

        destination_name = f"{source_hash}{suffix}" if suffix else source_hash
        destination = target_dir / destination_name

        if not await destination.exists():
            return CopyDecision(destination=destination, status=CopyStatus.DIRECT)

        try:
            existing_hash = await self._hasher.hash(destination)
        except OSError as error:
            if error.errno == errno.EINVAL:
                fallback = await self._next_available_hash_name(
                    target_dir,
                    source_hash,
                    suffix,
                )
                return CopyDecision(destination=fallback, status=CopyStatus.RENAMED)
            raise

        if existing_hash == source_hash:
            return CopyDecision(destination=None, status=CopyStatus.DUPLICATE)

        fallback = await self._next_available_hash_name(
            target_dir,
            source_hash,
            suffix,
        )
        return CopyDecision(destination=fallback, status=CopyStatus.RENAMED)

    async def _next_available_name(
        self,
        target_dir: AsyncPath,
        source_name: str,
    ) -> AsyncPath:
        """Find first free destination name with incremental numeric suffix."""
        source_stem = Path(source_name).stem
        source_suffix = Path(source_name).suffix
        index = 1

        while True:
            candidate = target_dir / f"{source_stem}_{index}{source_suffix}"
            if not await candidate.exists():
                return candidate
            index += 1

    async def _next_available_hash_name(
        self,
        target_dir: AsyncPath,
        source_hash: str,
        suffix: str,
    ) -> AsyncPath:
        """Find first free hash-based name with incremental numeric suffix."""
        index = 1
        while True:
            candidate_name = (
                f"{source_hash}_{index}{suffix}" if suffix else f"{source_hash}_{index}"
            )
            candidate = target_dir / candidate_name
            if not await candidate.exists():
                return candidate
            index += 1


class AioShutilFileCopier:
    """Default copier backed by aioshutil.copyfile."""

    async def copy(self, source_file: AsyncPath, destination: AsyncPath) -> None:
        await copyfile(source_file, destination)
