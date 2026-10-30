"""Safety checks for extracting untrusted archives (customer support bundles).

These guard against zip-slip / path traversal, decompression bombs, and
archives with an unreasonable number of entries. They are deliberately
conservative: a diagnostic bundle has no legitimate reason to contain
absolute paths, symlinks pointing outside itself, or multi-gigabyte members.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


class UnsafeArchiveError(Exception):
    """Raised when an archive member fails a safety check."""


@dataclass(frozen=True)
class ExtractionLimits:
    max_total_uncompressed_bytes: int = 20 * 1024 * 1024 * 1024  # 20 GiB
    max_member_uncompressed_bytes: int = 4 * 1024 * 1024 * 1024  # 4 GiB
    max_entries: int = 500_000
    max_compression_ratio: int = 1000


def resolve_safe_member_path(destination_dir: str, member_name: str) -> str:
    """Resolve an archive member name to a path under ``destination_dir``.

    Raises UnsafeArchiveError if the member would escape the destination
    directory (zip-slip), is an absolute path, or is a Windows drive-rooted
    path such as ``C:/...`` disguised with forward slashes.
    """
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        raise UnsafeArchiveError(f"Rejected absolute path in archive: {member_name!r}")

    dest_root = os.path.realpath(destination_dir)
    target = os.path.realpath(os.path.join(dest_root, normalized))

    if os.path.commonpath([dest_root, target]) != dest_root:
        raise UnsafeArchiveError(f"Rejected path escaping extraction root: {member_name!r}")

    # Real vm-support bundles nest per-VM diagnostic dump filenames (under
    # vmfs/volumes/<datastore>/<vm-name>/...) deep enough to exceed
    # Windows' traditional 260-character MAX_PATH. Using the \\?\
    # extended-length prefix lets *creation* succeed, but later
    # whole-tree operations (shutil.rmtree during cleanup, in particular)
    # do not apply that prefix themselves and fail on the same paths. It
    # is simpler and more robust to skip these few, consistently
    # host-health-irrelevant files outright than to fight MAX_PATH end to
    # end -- this is a documented, intentional limitation (see
    # SUPPORTED_FORMATS.md), not a silent data loss of anything a rule
    # or parser in this tool reads.
    if sys.platform == "win32" and len(target) > _WINDOWS_MAX_PATH_SAFE:
        raise UnsafeArchiveError(
            f"Path too long for this platform ({len(target)} chars), skipped: {member_name!r}"
        )

    return target


_WINDOWS_MAX_PATH_SAFE = 240


def check_member_size(
    member_name: str,
    compressed_size: int,
    uncompressed_size: int,
    limits: ExtractionLimits,
) -> None:
    if uncompressed_size > limits.max_member_uncompressed_bytes:
        raise UnsafeArchiveError(
            f"Member {member_name!r} exceeds max allowed size "
            f"({uncompressed_size} > {limits.max_member_uncompressed_bytes} bytes)"
        )
    if compressed_size > 0:
        ratio = uncompressed_size / compressed_size
        if ratio > limits.max_compression_ratio:
            raise UnsafeArchiveError(
                f"Member {member_name!r} has a suspicious compression ratio "
                f"({ratio:.0f}:1) and was rejected as a possible decompression bomb"
            )
