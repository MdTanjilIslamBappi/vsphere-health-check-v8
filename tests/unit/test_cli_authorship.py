from click.testing import CliRunner
from synthetic_bundle import build_tgz

from vhealth.cli import _resolve_authorship, main


def test_resolve_authorship_skips_prompt_when_not_a_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    authorship = _resolve_authorship(None, None, None, no_prompt=False)
    assert authorship.is_empty


def test_resolve_authorship_skips_prompt_when_no_prompt_flag(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    authorship = _resolve_authorship(None, None, None, no_prompt=True)
    assert authorship.is_empty


def test_resolve_authorship_prompts_only_for_missing_fields(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    prompted = []

    def fake_prompt(text, **kwargs):
        prompted.append(text)
        return "Prompted Verifier"

    monkeypatch.setattr("vhealth.cli.click.prompt", fake_prompt)
    authorship = _resolve_authorship(
        engineer_name="Given Engineer",
        report_author="Given Author",
        verifier_name=None,
        no_prompt=False,
    )
    assert authorship.engineer_name == "Given Engineer"
    assert authorship.author == "Given Author"
    assert authorship.verifier == "Prompted Verifier"
    assert len(prompted) == 1


def test_resolve_authorship_blank_prompt_answer_stays_unset(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("vhealth.cli.click.prompt", lambda text, **kwargs: "")
    authorship = _resolve_authorship(None, None, None, no_prompt=False)
    assert authorship.is_empty


def test_assess_with_authorship_flags_renders_on_cover_page(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    output_dir = tmp_path / "out"
    result = CliRunner().invoke(
        main,
        [
            "assess",
            "--input",
            str(bundle_path),
            "--output",
            str(output_dir),
            "--format",
            "html",
            "--engineer",
            "Test Engineer",
            "--author",
            "Test Author",
            "--verifier",
            "Test Verifier",
            "--no-prompt",
        ],
    )
    assert result.exit_code == 0, result.output
    html = (output_dir / "report.html").read_text(encoding="utf-8")
    assert "Test Engineer" in html
    assert "Test Author" in html
    assert "Test Verifier" in html


def test_assess_without_authorship_flags_omits_cover_fields(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    output_dir = tmp_path / "out"
    result = CliRunner().invoke(
        main,
        ["assess", "--input", str(bundle_path), "--output", str(output_dir), "--format", "html"],
    )
    assert result.exit_code == 0, result.output
    html = (output_dir / "report.html").read_text(encoding="utf-8")
    assert "Engineer:" not in html
    assert "Verified by:" not in html
