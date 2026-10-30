"""Secure, offline extraction of VMware support bundles (ZIP or .tar.gz).

No network access is ever performed here. Every archive is treated as
untrusted: member paths are validated against zip-slip, sizes are capped,
and a truncated/corrupt archive degrades to a partial result with a
warning rather than crashing the whole assessment.
"""

from __future__ import annotations

import os
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from vhealth.ingestion.exceptions import BundleCorruptError, UnsupportedBundleError
from vhealth.security.extraction_guard import (
    ExtractionLimits,
    UnsafeArchiveError,
    check_member_size,
    resolve_safe_member_path,
)

NESTED_ARCHIVE_SUFFIXES = (".tgz", ".tar.gz")


@dataclass
class ExtractionResult:
    root_dir: Path
    extracted_files: int = 0
    total_bytes: int = 0
    warnings: list[str] = field(default_factory=list)


def extract_bundle(
    input_path: Path,
    dest_dir: Path,
    limits: ExtractionLimits | None = None,
    _depth: int = 0,
) -> ExtractionResult:
    """Extract a support bundle archive into ``dest_dir``.

    Supports a top-level ZIP (vCenter support bundle) that may itself
    contain nested per-host ``.tgz``/``.tar.gz`` members (ESXi vm-support
    bundles), or a bare ``.tgz``/``.tar.gz`` (a single ESXi host bundle).
    """
    limits = limits or ExtractionLimits()
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(root_dir=dest_dir)

    is_zip, is_tar = _detect_archive_type(input_path)

    if is_zip:
        _extract_zip(input_path, dest_dir, limits, result)
    elif is_tar:
        _extract_tar(input_path, dest_dir, limits, result)
    elif input_path.name.endswith(NESTED_ARCHIVE_SUFFIXES):
        raise BundleCorruptError(
            f"{input_path} has a .tgz/.tar.gz name but could not be opened at all "
            "(likely truncated or corrupted before the first archive member)."
        )
    else:
        raise UnsupportedBundleError(
            f"{input_path} is neither a ZIP archive nor a gzip-compressed tar "
            "archive. Supply the diagnostic bundle exactly as exported by "
            "vm-support / vCenter (a .zip or .tgz file)."
        )

    if result.extracted_files == 0:
        raise BundleCorruptError(
            f"No files could be recovered from {input_path}. The archive is "
            "likely empty, fully corrupted, or encrypted."
        )

    if _depth == 0:
        _extract_nested_archives(dest_dir, limits, result)

    return result


def _detect_archive_type(input_path: Path) -> tuple[bool, bool]:
    """Sniff whether ``input_path`` is a ZIP or gzip-tar, tolerating corruption.

    ``tarfile.is_tarfile``/``zipfile.is_zipfile`` only catch their own
    library's "this isn't that format" errors -- a severely truncated
    gzip stream makes the underlying ``gzip`` module raise a plain
    ``EOFError`` while still reading the very first header, which is not
    a ``TarError`` and would otherwise propagate out of this function
    uncaught.
    """
    try:
        is_zip = zipfile.is_zipfile(input_path)
    except OSError:
        is_zip = False
    if is_zip:
        return True, False

    try:
        is_tar = tarfile.is_tarfile(input_path)
    except (OSError, EOFError, tarfile.TarError):
        is_tar = False
    return False, is_tar


def _extract_nested_archives(
    root_dir: Path, limits: ExtractionLimits, result: ExtractionResult
) -> None:
    """Expand per-host .tgz members found inside an extracted vCenter bundle."""
    for path in list(root_dir.rglob("*")):
        if not path.is_file():
            continue
        if not path.name.endswith(NESTED_ARCHIVE_SUFFIXES):
            continue
        # A matching suffix is only a hint: vm-support bundles contain files
        # like "fcdInfo.py.tgz" that are plain scripts, not archives, so the
        # actual content is sniffed before attempting to expand it.
        if not (zipfile.is_zipfile(path) or tarfile.is_tarfile(path)):
            continue
        nested_dest = path.parent / (path.name.rsplit(".", 1)[0] + ".extracted")
        try:
            nested_result = extract_bundle(path, nested_dest, limits, _depth=1)
        except (BundleCorruptError, UnsupportedBundleError) as exc:
            result.warnings.append(f"Could not expand nested archive {path.name}: {exc}")
            continue
        result.extracted_files += nested_result.extracted_files
        result.total_bytes += nested_result.total_bytes
        result.warnings.extend(nested_result.warnings)


def _extract_zip(
    input_path: Path, dest_dir: Path, limits: ExtractionLimits, result: ExtractionResult
) -> None:
    try:
        with zipfile.ZipFile(input_path) as zf:
            infos = zf.infolist()
            if len(infos) > limits.max_entries:
                raise UnsafeArchiveError(
                    f"Archive contains {len(infos)} entries, exceeding the limit "
                    f"of {limits.max_entries}"
                )
            for info in infos:
                if info.is_dir():
                    continue
                try:
                    check_member_size(
                        info.filename, info.compress_size, info.file_size, limits
                    )
                    target = resolve_safe_member_path(str(dest_dir), info.filename)
                except UnsafeArchiveError as exc:
                    result.warnings.append(str(exc))
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                result.extracted_files += 1
                result.total_bytes += info.file_size
                if result.total_bytes > limits.max_total_uncompressed_bytes:
                    raise UnsafeArchiveError(
                        "Archive exceeds the total extraction size limit "
                        f"({limits.max_total_uncompressed_bytes} bytes)"
                    )
    except zipfile.BadZipFile as exc:
        if result.extracted_files == 0:
            raise BundleCorruptError(f"{input_path} is not a valid ZIP file: {exc}") from exc
        result.warnings.append(f"ZIP archive ended early: {exc}")


def _extract_tar(
    input_path: Path, dest_dir: Path, limits: ExtractionLimits, result: ExtractionResult
) -> None:
    try:
        with tarfile.open(input_path, mode="r:gz") as tf:
            for member in tf:
                if result.extracted_files >= limits.max_entries:
                    raise UnsafeArchiveError(
                        f"Archive contains more than {limits.max_entries} entries"
                    )
                if not (member.isfile() or member.isdir()):
                    continue  # skip symlinks/devices/etc. from untrusted archives
                try:
                    check_member_size(member.name, member.size, member.size, limits)
                    target = resolve_safe_member_path(str(dest_dir), member.name)
                except UnsafeArchiveError as exc:
                    result.warnings.append(str(exc))
                    continue
                if member.isdir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                src = tf.extractfile(member)
                if src is None:
                    continue
                with open(target, "wb") as dst:
                    dst.write(src.read())
                result.extracted_files += 1
                result.total_bytes += member.size
                if result.total_bytes > limits.max_total_uncompressed_bytes:
                    raise UnsafeArchiveError(
                        "Archive exceeds the total extraction size limit "
                        f"({limits.max_total_uncompressed_bytes} bytes)"
                    )
    except (tarfile.ReadError, EOFError, OSError) as exc:
        if result.extracted_files == 0:
            raise BundleCorruptError(f"{input_path} could not be read: {exc}") from exc
        result.warnings.append(
            f"Extraction stopped early after recovering {result.extracted_files} files "
            f"(truncated archive or local I/O error): {exc}"
        )
