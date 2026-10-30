"""Filename edge cases that the Windows/Linux test matrix must cover."""

import zipfile

from vhealth.ingestion import extract_bundle


def test_extracts_unicode_and_spaced_filenames(tmp_path):
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("commands/café report.txt", "unicode and spaces")
        zf.writestr("etc/主机名.txt", "cjk filename")

    dest = tmp_path / "dest"
    result = extract_bundle(archive, dest)

    assert result.extracted_files == 2
    assert (dest / "commands" / "café report.txt").read_text(encoding="utf-8") == (
        "unicode and spaces"
    )


def test_extracts_into_destination_with_spaces_in_its_own_path(tmp_path):
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("commands/readme.txt", "hello")

    dest = tmp_path / "a destination with spaces"
    result = extract_bundle(archive, dest)

    assert result.extracted_files == 1
    assert (dest / "commands" / "readme.txt").is_file()
