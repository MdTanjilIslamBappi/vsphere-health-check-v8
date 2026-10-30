from click.testing import CliRunner
from synthetic_bundle import build_tgz

from vhealth.cli import main


def test_version_flag():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "vhealth" in result.output


def test_inspect_reports_host_count(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    result = CliRunner().invoke(main, ["inspect", "--input", str(bundle_path)])
    assert result.exit_code == 0
    assert "ESXi host bundles found: 1" in result.output


def test_inspect_on_non_archive_file_fails_cleanly(tmp_path):
    bogus = tmp_path / "not-an-archive.zip"
    bogus.write_text("this is not a zip file")
    result = CliRunner().invoke(main, ["inspect", "--input", str(bogus)])
    assert result.exit_code == 2
    assert "error:" in result.output


def test_assess_writes_assessment_json_and_reports(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz", smart_health="FAILED")
    output_dir = tmp_path / "out"
    result = CliRunner().invoke(
        main, ["assess", "--input", str(bundle_path), "--output", str(output_dir)]
    )
    assert result.exit_code == 0, result.output
    assert (output_dir / "assessment.json").is_file()
    assert (output_dir / "report.html").is_file()
    assert (output_dir / "report.docx").is_file()
    assert "1 finding" in result.output or "finding(s)" in result.output


def test_assess_html_only(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    output_dir = tmp_path / "out"
    result = CliRunner().invoke(
        main,
        ["assess", "--input", str(bundle_path), "--output", str(output_dir), "--format", "html"],
    )
    assert result.exit_code == 0, result.output
    assert (output_dir / "report.html").is_file()
    assert not (output_dir / "report.docx").is_file()


def test_assess_accepts_positional_bundle_and_output_paths(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    output_dir = tmp_path / "out"
    result = CliRunner().invoke(main, ["assess", str(bundle_path), str(output_dir)])
    assert result.exit_code == 0, result.output
    assert (output_dir / "assessment.json").is_file()
    assert f"Report location: {output_dir}" in result.output


def test_assess_defaults_output_to_a_temp_dir_when_omitted(tmp_path, monkeypatch):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    fake_tmp_root = tmp_path / "fake-tmp"
    fake_tmp_root.mkdir()
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(fake_tmp_root))

    result = CliRunner().invoke(main, ["assess", str(bundle_path)])
    assert result.exit_code == 0, result.output
    assert "No output directory was given" in result.output
    written = list(fake_tmp_root.glob("vhealth-report-*/assessment.json"))
    assert len(written) == 1
    assert f"Report location: {written[0].parent}" in result.output


def test_assess_without_any_bundle_path_fails_with_a_clear_usage_error():
    result = CliRunner().invoke(main, ["assess"])
    assert result.exit_code != 0
    assert "Missing the support bundle path" in result.output


def test_report_regenerates_from_saved_assessment(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    assess_dir = tmp_path / "out"
    CliRunner().invoke(main, ["assess", "--input", str(bundle_path), "--output", str(assess_dir)])

    report_dir = tmp_path / "re-report"
    result = CliRunner().invoke(
        main,
        [
            "report",
            "--assessment",
            str(assess_dir / "assessment.json"),
            "--output",
            str(report_dir),
            "--format",
            "html",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (report_dir / "report.html").is_file()
