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
from vhealth.reporting import write_docx_report, write_html_report

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_UNEXPECTED_ERROR = 3


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
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the customer-supplied support bundle (.zip or .tgz).",
)
@click.option(
    "--output",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write assessment.json and reports into.",
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
def assess(
    input_path: Path, output_dir: Path, config_path: Path | None, formats: str, keep_extracted: bool
) -> None:
    """Run ingestion, parsing, correlation and rules, then write reports."""
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

    _generate_reports(assessment, config, output_dir, formats)

    if not keep_extracted:
        for child in output_dir.iterdir():
            if child.is_dir() and child.name.startswith("vhealth-extract-"):
                shutil.rmtree(child, ignore_errors=True)

    click.echo(
        f"Assessment complete: {len(assessment.hosts)} host(s), "
        f"{len(assessment.findings)} finding(s)."
    )
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
def report(assessment_path: Path, formats: str, output_dir: Path, config_path: Path | None) -> None:
    """Re-render reports from an existing assessment.json, without re-parsing the bundle."""
    try:
        assessment = Assessment.model_validate_json(assessment_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: could not read assessment file: {exc}", err=True)
        sys.exit(EXIT_INPUT_ERROR)

    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    _generate_reports(assessment, config, output_dir, formats)
    sys.exit(EXIT_OK)


def _generate_reports(assessment: Assessment, config, output_dir: Path, formats: str) -> None:
    requested = {f.strip().lower() for f in formats.split(",") if f.strip()}
    if "html" in requested:
        html_path = output_dir / "report.html"
        write_html_report(assessment, config, html_path)
        click.echo(f"Wrote {html_path}")
    if "docx" in requested:
        docx_path = output_dir / "report.docx"
        write_docx_report(assessment, config, docx_path)
        click.echo(f"Wrote {docx_path}")


if __name__ == "__main__":
    main()
