import sys

import pytest

from vhealth.security.extraction_guard import (
    ExtractionLimits,
    UnsafeArchiveError,
    check_member_size,
    resolve_safe_member_path,
)


def test_rejects_parent_directory_traversal(tmp_path):
    with pytest.raises(UnsafeArchiveError):
        resolve_safe_member_path(str(tmp_path), "../../evil.txt")


def test_rejects_absolute_path(tmp_path):
    with pytest.raises(UnsafeArchiveError):
        resolve_safe_member_path(str(tmp_path), "/etc/passwd")


def test_rejects_windows_drive_path(tmp_path):
    with pytest.raises(UnsafeArchiveError):
        resolve_safe_member_path(str(tmp_path), "C:/Windows/System32/evil.dll")


def test_accepts_normal_relative_path(tmp_path):
    target = resolve_safe_member_path(str(tmp_path), "commands/uname_-a.txt")
    assert str(tmp_path) in target
    assert target.endswith("uname_-a.txt")


def test_accepts_unicode_and_spaced_path(tmp_path):
    target = resolve_safe_member_path(str(tmp_path), "etc/vm name/caf\u00e9.txt")
    assert "caf\u00e9.txt" in target


@pytest.mark.skipif(sys.platform != "win32", reason="MAX_PATH only applies on Windows")
def test_rejects_path_over_windows_max_path(tmp_path):
    long_name = "a" * 260
    with pytest.raises(UnsafeArchiveError):
        resolve_safe_member_path(str(tmp_path), long_name)


def test_check_member_size_rejects_oversized_member():
    limits = ExtractionLimits(max_member_uncompressed_bytes=100)
    with pytest.raises(UnsafeArchiveError):
        check_member_size("big.bin", compressed_size=10, uncompressed_size=1000, limits=limits)


def test_check_member_size_rejects_decompression_bomb():
    limits = ExtractionLimits(max_compression_ratio=100)
    with pytest.raises(UnsafeArchiveError):
        check_member_size(
            "bomb.bin", compressed_size=10, uncompressed_size=1_000_000, limits=limits
        )


def test_check_member_size_accepts_normal_ratio():
    limits = ExtractionLimits()
    check_member_size("normal.bin", compressed_size=1000, uncompressed_size=3000, limits=limits)
