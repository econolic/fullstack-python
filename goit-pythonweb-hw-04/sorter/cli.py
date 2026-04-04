from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import logging
import platform
from pathlib import Path

from aiopath import AsyncPath

from sorter.maintenance import LocalEmptyDirectoryCleaner, LocalSourceFileRemover
from sorter.models import SortStats
from sorter.service import AsyncFileSorter
from sorter.strategies import (
    AioShutilFileCopier,
    HashCollisionResolver,
    HashNameCollisionResolver,
    Sha256FileHasher,
    SuffixExtensionResolver,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_REPORT_FILENAME = "sort_report.txt"
REPORT_TO_OUTPUT_SENTINEL = "__report_to_output_default__"


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Asynchronously sort files by extension.",
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source folder to scan recursively.",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Destination folder for sorted files.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Maximum number of concurrent copy tasks (default: 10).",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=None,
        metavar="EXT",
        help=(
            "Optional list of file types to sort (e.g. txt jpg png or .txt .jpg). "
            "Other types are skipped."
        ),
    )
    parser.add_argument(
        "--exclude-types",
        nargs="+",
        default=None,
        metavar="EXT",
        help=(
            "Optional list of file types to exclude from processing "
            "(e.g. tmp db, no_extension)."
        ),
    )
    parser.add_argument(
        "--name-by-hash",
        action="store_true",
        help="Store copied files with hash-based names inside each type folder.",
    )
    parser.add_argument(
        "--move-files",
        action="store_true",
        help="Delete source files after successful copy/merge into output.",
    )
    parser.add_argument(
        "--cleanup-empty-dirs",
        action="store_true",
        help=(
            "Delete empty directories in source after transfer. "
            "Intended for use with --move-files."
        ),
    )
    parser.add_argument(
        "--report-file",
        nargs="?",
        type=str,
        const=REPORT_TO_OUTPUT_SENTINEL,
        default=None,
        metavar="REPORT_PATH",
        help=(
            "Optional report path. Use --report-file with no value to save "
            "sort_report.txt into OUTPUT_FOLDER."
        ),
    )
    return parser


def resolve_report_path(report_argument: str, output_path: Path) -> Path:
    """Resolve final report path based on CLI argument semantics."""
    if report_argument == REPORT_TO_OUTPUT_SENTINEL:
        return (output_path / DEFAULT_REPORT_FILENAME).resolve()

    candidate = Path(report_argument).expanduser()

    if candidate.exists() and candidate.is_dir():
        return (candidate / DEFAULT_REPORT_FILENAME).resolve()

    return candidate.resolve()


def normalize_extensions(raw_types: list[str] | None) -> set[str] | None:
    """Normalize CLI extension tokens to lowercase names without leading dot."""
    if not raw_types:
        return None

    normalized: set[str] = set()
    for token in raw_types:
        for part in token.split(","):
            item = part.strip().lower().lstrip(".")
            if item:
                normalized.add(item)

    return normalized if normalized else None


def format_bytes(size_in_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    value = float(size_in_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{size_in_bytes} B"


def build_report_text(source: Path, output: Path, stats: SortStats) -> str:
    """Build plain text report content from collected statistics."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    estimated_without_dedup = stats.copied_bytes + stats.deduplicated_bytes

    lines = [
        "File Sorting Report",
        f"Generated at: {generated_at}",
        f"Source folder: {source}",
        f"Output folder: {output}",
        "",
        "Totals:",
        f"- Scanned files: {stats.scanned}",
        f"- Copied files: {stats.copied}",
        f"- Renamed files on collision: {stats.renamed}",
        f"- Duplicates detected: {stats.duplicates_detected}",
        f"- Duplicates merged: {stats.duplicates_merged}",
        f"- Failed files: {stats.failed}",
        f"- Source files deleted: {stats.source_deleted}",
        f"- Source delete errors: {stats.source_delete_failed}",
        f"- Source empty dirs deleted: {stats.source_dirs_deleted}",
        f"- Source dir delete errors: {stats.source_dir_delete_failed}",
        "",
        "Size metrics:",
        (
            f"- Processed input size: {stats.processed_bytes} bytes "
            f"({format_bytes(stats.processed_bytes)})"
        ),
        (
            f"- Copied size: {stats.copied_bytes} bytes "
            f"({format_bytes(stats.copied_bytes)})"
        ),
        (
            f"- Deduplicated (saved) size: {stats.deduplicated_bytes} bytes "
            f"({format_bytes(stats.deduplicated_bytes)})"
        ),
        (
            f"- Source size removed: {stats.source_deleted_bytes} bytes "
            f"({format_bytes(stats.source_deleted_bytes)})"
        ),
        (
            f"- Estimated size without deduplication (this run): "
            f"{estimated_without_dedup} bytes "
            f"({format_bytes(estimated_without_dedup)})"
        ),
        (
            f"- Current output folder size: {stats.output_size_bytes} bytes "
            f"({format_bytes(stats.output_size_bytes)})"
        ),
        "",
        "Copied files by type:",
    ]

    if stats.copied_by_extension:
        sorted_extensions = sorted(
            stats.copied_by_extension.items(),
            key=lambda item: (-item[1], item[0]),
        )
        for extension, count in sorted_extensions:
            bytes_for_type = stats.copied_bytes_by_extension.get(extension, 0)
            lines.append(
                f"- {extension}: {count} files, {bytes_for_type} bytes "
                f"({format_bytes(bytes_for_type)})"
            )
    else:
        lines.append("- no files copied")

    return "\n".join(lines) + "\n"


async def write_report_file(
    report_path: Path,
    text: str,
) -> None:
    """Write text report to a UTF-8 file."""
    await asyncio.to_thread(
        lambda: report_path.parent.mkdir(parents=True, exist_ok=True)
    )
    await asyncio.to_thread(report_path.write_text, text, encoding="utf-8")


def build_sorter(
    source_dir: AsyncPath,
    output_dir: AsyncPath,
    workers: int,
    allowed_extensions: set[str] | None,
    excluded_extensions: set[str],
    name_by_hash: bool,
    move_files: bool,
    cleanup_empty_dirs: bool,
) -> AsyncFileSorter:
    """Build default sorter with pluggable implementations."""
    extension_resolver = SuffixExtensionResolver()
    hasher = Sha256FileHasher()
    if name_by_hash:
        collision_resolver = HashNameCollisionResolver(hasher)
    else:
        collision_resolver = HashCollisionResolver(hasher)
    file_copier = AioShutilFileCopier()
    source_file_remover = LocalSourceFileRemover()
    empty_directory_cleaner = LocalEmptyDirectoryCleaner(Path(str(output_dir)))

    return AsyncFileSorter(
        source_dir=source_dir,
        output_dir=output_dir,
        workers=workers,
        allowed_extensions=allowed_extensions,
        excluded_extensions=excluded_extensions,
        move_files=move_files,
        cleanup_empty_dirs=cleanup_empty_dirs,
        extension_resolver=extension_resolver,
        collision_resolver=collision_resolver,
        file_copier=file_copier,
        source_file_remover=source_file_remover,
        empty_directory_cleaner=empty_directory_cleaner,
    )


def validate_source(source: Path) -> Path:
    """Validate and normalize source path."""
    source_resolved = source.expanduser().resolve()
    if not source_resolved.exists():
        raise FileNotFoundError(f"Source folder does not exist: {source_resolved}")
    if not source_resolved.is_dir():
        raise NotADirectoryError(f"Source path is not a folder: {source_resolved}")
    return source_resolved


def normalize_output(output: Path) -> Path:
    """Normalize and create output path if needed."""
    output_resolved = output.expanduser().resolve()
    output_resolved.mkdir(parents=True, exist_ok=True)
    return output_resolved


async def async_main(arguments: argparse.Namespace) -> int:
    """Main asynchronous workflow."""
    source_path = AsyncPath(validate_source(arguments.source))
    output_path = AsyncPath(normalize_output(arguments.output))
    source_fs_path = Path(str(source_path))
    output_fs_path = Path(str(output_path))

    LOGGER.info("Source folder: %s", source_path)
    LOGGER.info("Output folder: %s", output_path)
    LOGGER.info("Workers: %s", arguments.workers)
    allowed_extensions = normalize_extensions(arguments.types)
    excluded_extensions = normalize_extensions(arguments.exclude_types) or set()

    if allowed_extensions is not None and excluded_extensions:
        allowed_extensions = {
            ext for ext in allowed_extensions if ext not in excluded_extensions
        }
        if not allowed_extensions:
            LOGGER.warning(
                "All selected --types are excluded by --exclude-types; nothing will be processed."
            )

    if allowed_extensions is not None:
        LOGGER.info("Enabled type filter: %s", ", ".join(sorted(allowed_extensions)))
    if excluded_extensions:
        LOGGER.info("Excluded types: %s", ", ".join(sorted(excluded_extensions)))
    LOGGER.info("Hash-based naming: %s", arguments.name_by_hash)
    LOGGER.info("Move mode (delete source after transfer): %s", arguments.move_files)
    LOGGER.info(
        "Cleanup empty source dirs: %s",
        arguments.cleanup_empty_dirs,
    )

    if arguments.cleanup_empty_dirs and not arguments.move_files:
        LOGGER.warning(
            "--cleanup-empty-dirs has effect mainly with --move-files; without move mode most source dirs are not empty."
        )

    sorter = build_sorter(
        source_path,
        output_path,
        arguments.workers,
        allowed_extensions,
        excluded_extensions,
        arguments.name_by_hash,
        arguments.move_files,
        arguments.cleanup_empty_dirs,
    )
    stats = await sorter.run()

    LOGGER.info(
        (
            "Completed. scanned=%d copied=%d renamed=%d skipped_duplicates=%d "
            "failed=%d source_deleted=%d source_delete_failed=%d "
            "source_dirs_deleted=%d source_dir_delete_failed=%d "
            "processed_bytes=%d copied_bytes=%d deduplicated_bytes=%d "
            "source_deleted_bytes=%d output_size_bytes=%d"
        ),
        stats.scanned,
        stats.copied,
        stats.renamed,
        stats.skipped_duplicates,
        stats.failed,
        stats.source_deleted,
        stats.source_delete_failed,
        stats.source_dirs_deleted,
        stats.source_dir_delete_failed,
        stats.processed_bytes,
        stats.copied_bytes,
        stats.deduplicated_bytes,
        stats.source_deleted_bytes,
        stats.output_size_bytes,
    )

    if arguments.report_file is not None:
        report_path = resolve_report_path(arguments.report_file, output_fs_path)
        report_text = build_report_text(source_fs_path, output_fs_path, stats)
        await write_report_file(report_path, report_text)
        LOGGER.info("Report written to %s", report_path)

    return 0 if stats.failed == 0 else 1


def main() -> int:
    """CLI entry point."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.workers < 1:
        LOGGER.error("--workers must be a positive integer")
        return 2

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        return asyncio.run(async_main(args))
    except (FileNotFoundError, NotADirectoryError) as error:
        LOGGER.error("Input validation failed: %s", error)
        return 2
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Unexpected error: %s", error)
        return 1
