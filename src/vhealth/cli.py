from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import click

from vhealth import __version__
from vhealth.config import load_config
from vhealth.discovery import find_host_bundles
from vhealth.ingestion import extract_bundle
from vhealth.ingestion.exceptions import VHealthError
from vhealth.models.assessment import Assessment
from vhealth.pipeline import run_assessment
from vhealth.reporting import (
    ReportAuthorship,
    write_docx_findings_log,
    write_docx_report,
    write_html_findings_log,
    write_html_report,
)

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_UNEXPECTED_ERROR = 3


def _authorship_options(f):
    """Shared report-metadata options for report-producing commands."""
    f = click.option(
        "--description",
        "revision_description",
        default="Initial copy",
        show_default=True,
        help="Description shown in the report's Version History table.",
    )(f)
    f = click.option(
        "--revision",
        "revision",
        default="V01",
        show_default=True,
        help="Revision label shown in the report's Version History table.",
    )(f)
    f = click.option(
        "--verifier",
        "verifier_name",
        default=None,
        help="Name of the person who verified/reviewed this report; shown on the cover page.",
    )(f)
    f = click.option(
        "--author",
        "report_author",
        default=None,
        help="Name of this report version's author; shown on the cover page.",
    )(f)
    f = click.option(
        "--engineer",
        "engineer_name",
        default=None,
        help="Name of the engineer who performed the assessment; shown on the cover page.",
    )(f)
    f = click.option(
        "--no-prompt",
        is_flag=True,
        default=False,
        help="Never prompt interactively for engineer/author/verifier; leave any unset.",
    )(f)
    return f


def _resolve_authorship(
    engineer_name: str | None,
    report_author: str | None,
    verifier_name: str | None,
    no_prompt: bool,
    revision: str = "V01",
    revision_description: str = "Initial copy",
) -> ReportAuthorship:
    """Fill in any of engineer/author/verifier not given on the command line.

    Only prompts interactively when attached to a real terminal and
    --no-prompt was not given; a non-interactive run (CI, a script) simply
    leaves whatever was not passed as a flag unset rather than hanging.

    ``sys.stdin.isatty()`` is only a best-effort signal -- some automation
    contexts (e.g. a pty-wrapped shell) report a tty with nobody present to
    answer. If a prompt hits EOF/abort anyway, treat it the same as
    --no-prompt instead of propagating the error.
    """
    if no_prompt or not sys.stdin.isatty():
        return ReportAuthorship(
            engineer_name=engineer_name,
            author=report_author,
            verifier=verifier_name,
            revision=revision,
            description=revision_description,
        )

    try:
        if engineer_name is None:
            engineer_name = click.prompt(
                "Engineer name (for the report cover page, press Enter to skip)",
                default="",
                show_default=False,
            ).strip() or None
        if report_author is None:
            report_author = click.prompt(
                "Report author (press Enter to skip)", default="", show_default=False
            ).strip() or None
        if verifier_name is None:
            verifier_name = click.prompt(
                "Verified by (press Enter to skip)", default="", show_default=False
            ).strip() or None
    except (EOFError, click.exceptions.Abort):
        pass

    return ReportAuthorship(
        engineer_name=engineer_name,
        author=report_author,
        verifier=verifier_name,
        revision=revision,
        description=revision_description,
    )


@click.group()
@click.version_option(version=__version__, prog_name="vhealth")
def main() -> None:
    """vhealth: offline VMware vSphere support-bundle health assessment."""


@main.command()
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the customer-supplied support bundle (.zip or .tgz).",
)
def inspect(input_path: Path) -> None:
    """Report what a support bundle contains, without producing an assessment."""
    config = load_config(None)
    with tempfile.TemporaryDirectory(
        prefix="vhealth-inspect-", ignore_cleanup_errors=True
    ) as tmp:
        tmp_dir = Path(tmp)
        try:
            result = extract_bundle(input_path, tmp_dir, config.extraction_limits)
        except VHealthError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(EXIT_INPUT_ERROR)

        host_refs = find_host_bundles(tmp_dir)
        click.echo(f"Input file:       {input_path}")
        click.echo(f"Files extracted:  {result.extracted_files}")
        click.echo(f"Total size:       {result.total_bytes / (1024 * 1024):.1f} MiB")
        if result.warnings:
            click.echo(f"Warnings:         {len(result.warnings)}")
            for w in result.warnings[:10]:
                click.echo(f"  - {w}")
        click.echo(f"ESXi host bundles found: {len(host_refs)}")
        for ref in host_refs:
            click.echo(f"  - {ref.hostname_hint} ({ref.root.name})")
    sys.exit(EXIT_OK)


@main.command()
@click.argument(
    "input_arg",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="BUNDLE_ZIP",
)
@click.argument(
    "output_arg",
    required=False,
    type=click.Path(file_okay=False, path_type=Path),
    metavar="[OUTPUT_DIR]",
)
@click.option(
    "--input",
    "input_opt",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the customer-supplied support bundle (.zip or .tgz). "
    "Can also be given as the first plain argument.",
)
@click.option(
    "--output",
    "output_opt",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory to write assessment.json and reports into. Can also be given "
    "as the second plain argument. If not given at all, a new folder under the "
    "system temp directory is used and its path is printed at the end.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional TOML configuration file overriding the bundled defaults.",
)
@click.option(
    "--format",
    "formats",
    default="docx,html",
    help="Comma-separated report formats to generate: docx, html, or none.",
)
@click.option(
    "--keep-extracted",
    is_flag=True,
    default=False,
    help="Do not delete the extracted bundle contents after assessment.",
)
@_authorship_options
def assess(
    input_arg: Path | None,
    output_arg: Path | None,
    input_opt: Path | None,
    output_opt: Path | None,
    config_path: Path | None,
    formats: str,
    keep_extracted: bool,
    engineer_name: str | None,
    report_author: str | None,
    verifier_name: str | None,
    no_prompt: bool,
    revision: str,
    revision_description: str,
) -> None:
    """Run ingestion, parsing, correlation and rules, then write reports.

    Simplest form, one line: `vhealth assess /path/to/support-bundle.zip
    /path/to/output`. The output directory may be omitted entirely --
    `vhealth assess /path/to/support-bundle.zip` -- in which case a new
    folder under the system temp directory is used instead, and its path
    is printed once the report is written.
    """
    input_path = input_opt or input_arg
    if input_path is None:
        raise click.UsageError(
            "Missing the support bundle path. Example: "
            "vhealth assess support-bundle.zip [output-dir]"
        )

    output_dir = output_opt or output_arg
    output_was_defaulted = output_dir is None
    if output_was_defaulted:
        output_dir = Path(tempfile.mkdtemp(prefix="vhealth-report-"))

    authorship = _resolve_authorship(
        engineer_name, report_author, verifier_name, no_prompt, revision, revision_description
    )

    try:
        config = load_config(config_path)
        assessment = run_assessment(input_path, output_dir, config)
    except VHealthError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_INPUT_ERROR)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"unexpected error during assessment: {exc}", err=True)
        sys.exit(EXIT_UNEXPECTED_ERROR)

    assessment_path = output_dir / "assessment.json"
    assessment_path.write_text(assessment.model_dump_json(indent=2), encoding="utf-8")
    click.echo(f"Wrote {assessment_path}")

    _generate_reports(assessment, config, output_dir, formats, authorship)

    if not keep_extracted:
        for child in output_dir.iterdir():
            if child.is_dir() and child.name.startswith("vhealth-extract-"):
                shutil.rmtree(child, ignore_errors=True)

    click.echo(
        f"Assessment complete: {len(assessment.hosts)} host(s), "
        f"{len(assessment.findings)} finding(s)."
    )
    if output_was_defaulted:
        click.echo("No output directory was given, so a temp folder was used.")
    click.echo(f"Report location: {output_dir}")
    sys.exit(EXIT_OK)


@main.command()
@click.option(
    "--assessment",
    "assessment_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a previously generated assessment.json.",
)
@click.option(
    "--format",
    "formats",
    default="docx,html",
    help="Comma-separated report formats to generate: docx, html.",
)
@click.option(
    "--output",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write reports into.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional TOML configuration file overriding the bundled defaults.",
)
@_authorship_options
def report(
    assessment_path: Path,
    formats: str,
    output_dir: Path,
    config_path: Path | None,
    engineer_name: str | None,
    report_author: str | None,
    verifier_name: str | None,
    no_prompt: bool,
    revision: str,
    revision_description: str,
) -> None:
    """Re-render reports from an existing assessment.json, without re-parsing the bundle."""
    authorship = _resolve_authorship(
        engineer_name, report_author, verifier_name, no_prompt, revision, revision_description
    )

    try:
        assessment = Assessment.model_validate_json(assessment_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: could not read assessment file: {exc}", err=True)
        sys.exit(EXIT_INPUT_ERROR)

    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    _generate_reports(assessment, config, output_dir, formats, authorship)
    sys.exit(EXIT_OK)


def _generate_reports(
    assessment: Assessment,
    config,
    output_dir: Path,
    formats: str,
    authorship: ReportAuthorship | None = None,
) -> None:
    requested = {f.strip().lower() for f in formats.split(",") if f.strip()}
    if "html" in requested:
        html_path = output_dir / "report.html"
        write_html_report(assessment, config, html_path, authorship)
        click.echo(f"Wrote {html_path}")
        findings_log_path = output_dir / "findings-log.html"
        write_html_findings_log(assessment, config, findings_log_path, authorship)
        click.echo(f"Wrote {findings_log_path}")
    if "docx" in requested:
        docx_path = output_dir / "report.docx"
        write_docx_report(assessment, config, docx_path, authorship)
        click.echo(f"Wrote {docx_path}")
        findings_log_path = output_dir / "findings-log.docx"
        write_docx_findings_log(assessment, config, findings_log_path, authorship)
        click.echo(f"Wrote {findings_log_path}")


if __name__ == "__main__":
    main()
