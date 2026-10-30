"""The detailed, per-finding log -- a companion document to the main report.

The main executive-style report (``docx_report.py``/``html_report.py``)
intentionally does not dump every individual finding inline; this module
writes that raw, evidence-level detail to its own file instead, so the
main report stays readable while nothing is lost -- every finding (full
summary, evidence lines, remediation, limitations) is still written down
somewhere.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from jinja2 import Environment

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.models.findings import Severity
from vhealth.reporting.authorship import ReportAuthorship

VERSION = "1.0.0"

_SEVERITY_COLOR = {
    Severity.CRITICAL: RGBColor(0xB3, 0x00, 0x00),
    Severity.HIGH: RGBColor(0xD9, 0x53, 0x4F),
    Severity.MEDIUM: RGBColor(0xC7, 0x7C, 0x00),
    Severity.LOW: RGBColor(0x5B, 0x8D, 0xEF),
    Severity.INFO: RGBColor(0x6C, 0x75, 0x7D),
}

_TEMPLATE_PATH = "templates/findings_log.html.j2"


def write_docx_findings_log(
    assessment: Assessment,
    config: AssessmentConfig,
    output_path: Path,
    authorship: ReportAuthorship | None = None,
) -> None:
    authorship = authorship or ReportAuthorship()
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(f"{config.report.title} -- Detailed Findings Log")
    run.font.size = Pt(22)
    run.font.bold = True

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"Companion to the main report generated {assessment.metadata.assessment_timestamp}\n"
        f"Input: {assessment.metadata.input_filename}\n"
        f"SHA-256: {assessment.metadata.input_sha256}\n"
        f"Assessment schema: {assessment.metadata.schema_version} · "
        f"vhealth {assessment.metadata.app_version} · "
        f"rule engine {assessment.metadata.rule_engine_version}"
    ).font.size = Pt(9)
    doc.add_page_break()

    findings = sorted(assessment.findings, key=lambda f: -f.severity.rank)
    if not findings:
        doc.add_paragraph("No findings were raised by the checks that could run for this bundle.")
    for finding in findings:
        heading = doc.add_paragraph()
        run = heading.add_run(f"[{finding.severity.value.upper()}] {finding.title}")
        run.bold = True
        run.font.color.rgb = _SEVERITY_COLOR[finding.severity]

        meta_line = finding.rule_id
        if finding.affected_host:
            meta_line += f" · {finding.affected_host}"
        if finding.affected_object:
            meta_line += f" · {finding.affected_object}"
        meta_p = doc.add_paragraph()
        meta_p.add_run(meta_line).italic = True

        doc.add_paragraph(finding.summary)
        if finding.remediation:
            p = doc.add_paragraph()
            p.add_run("Remediation: ").bold = True
            p.add_run(finding.remediation)
        if finding.limitations:
            p = doc.add_paragraph()
            p.add_run("Limitations: ").bold = True
            p.add_run(finding.limitations)
        for line in finding.evidence:
            doc.add_paragraph(line, style="Intense Quote")

    if assessment.metadata.processing_warnings:
        doc.add_page_break()
        doc.add_heading("Processing Warnings", level=1)
        for w in assessment.metadata.processing_warnings:
            doc.add_paragraph(f"{w.source}: {w.message}", style="List Bullet")

    doc.save(str(output_path))


def write_html_findings_log(
    assessment: Assessment,
    config: AssessmentConfig,
    output_path: Path,
    authorship: ReportAuthorship | None = None,
) -> None:
    template_text = (
        resources.files("vhealth.resources").joinpath(_TEMPLATE_PATH).read_text(encoding="utf-8")
    )
    env = Environment(autoescape=True)
    template = env.from_string(template_text)

    html = template.render(
        assessment=assessment,
        config=config,
        authorship=authorship or ReportAuthorship(),
        findings=sorted(assessment.findings, key=lambda f: -f.severity.rank),
    )
    output_path.write_text(html, encoding="utf-8")
