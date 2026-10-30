"""End-to-end extraction tests against deliberately hostile archives.

These exercise the full extract_bundle() path (not just the guard
functions in isolation) to confirm a malicious or malformed archive
degrades to a warning instead of writing outside the destination
directory or crashing the process.
"""

import tarfile
import zipfile

import pytest

from vhealth.ingestion import BundleCorruptError, UnsupportedBundleError, extract_bundle


def test_zip_slip_member_is_not_written_outside_destination(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../escaped.txt", "pwned")
        zf.writestr("safe/inside.txt", "fine")

    dest = tmp_path / "dest"
    canary = tmp_path.parent / "escaped.txt"
    canary.unlink(missing_ok=True)

    result = extract_bundle(archive, dest)

    assert not canary.exists()
    assert (dest / "safe" / "inside.txt").is_file()
    assert any("escaping extraction root" in w for w in result.warnings)


def test_tar_slip_member_is_not_written_outside_destination(tmp_path):
    archive = tmp_path / "evil.tgz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name="../../escaped.txt")
        data = b"pwned"
        info.size = len(data)
        import io

        tf.addfile(info, io.BytesIO(data))
        info2 = tarfile.TarInfo(name="safe/inside.txt")
        data2 = b"fine"
        info2.size = len(data2)
        tf.addfile(info2, io.BytesIO(data2))

    dest = tmp_path / "dest"
    canary = tmp_path.parent / "escaped.txt"
    canary.unlink(missing_ok=True)

    extract_bundle(archive, dest)

    assert not canary.exists()
    assert (dest / "safe" / "inside.txt").is_file()


def test_non_archive_file_raises_unsupported_bundle_error(tmp_path):
    bogus = tmp_path / "not-an-archive.zip"
    bogus.write_bytes(b"not a real archive")
    with pytest.raises(UnsupportedBundleError):
        extract_bundle(bogus, tmp_path / "dest")


def test_truncated_gzip_degrades_to_partial_result(tmp_path):
    archive = tmp_path / "truncated.tgz"
    with tarfile.open(archive, "w:gz") as tf:
        for i in range(5):
            data = f"content {i}".encode()
            info = tarfile.TarInfo(name=f"file{i}.txt")
            info.size = len(data)
            import io

            tf.addfile(info, io.BytesIO(data))

    raw = bytearray(archive.read_bytes())
    archive.write_bytes(bytes(raw[: len(raw) // 2]))

    dest = tmp_path / "dest"
    try:
        result = extract_bundle(archive, dest)
    except BundleCorruptError:
        pass
    else:
        assert result.extracted_files >= 0
        assert result.warnings


def test_empty_zip_raises_bundle_corrupt_error(tmp_path):
    archive = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive, "w"):
        pass
    with pytest.raises(BundleCorruptError):
        extract_bundle(archive, tmp_path / "dest")
