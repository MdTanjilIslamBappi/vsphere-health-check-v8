from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.models.findings import Severity

VERSION = "1.0.0"

_SEVERITY_COLOR = {
    Severity.CRITICAL: RGBColor(0xB3, 0x00, 0x00),
    Severity.HIGH: RGBColor(0xD9, 0x53, 0x4F),
    Severity.MEDIUM: RGBColor(0xC7, 0x7C, 0x00),
    Severity.LOW: RGBColor(0x5B, 0x8D, 0xEF),
    Severity.INFO: RGBColor(0x6C, 0x75, 0x7D),
}


def write_docx_report(assessment: Assessment, config: AssessmentConfig, output_path: Path) -> None:
    doc = Document()

    _add_title_page(doc, assessment, config)
    doc.add_page_break()

    doc.add_heading("1. Executive Summary", level=1)
    _add_executive_summary(doc, assessment)

    doc.add_heading("2. Scope of Health Check", level=1)
    _add_scope(doc, assessment)

    doc.add_heading("3. System Status", level=1)
    doc.add_heading("3.1 Current Hardware Status", level=2)
    _add_hardware_status(doc, assessment)

    doc.add_heading("3.2 Current State Analysis of VMware Components", level=2)
    _add_storage_components(doc, assessment)

    doc.add_heading("3.3 Current State Analysis of ESXi Hosts — Findings", level=2)
    _add_findings(doc, assessment)

    doc.add_heading("3.4 Recommendation", level=2)
    doc.add_paragraph(
        "Review each finding above in severity order. Critical and high-severity findings "
        "should be investigated before the next maintenance window; medium/low findings "
        "should be tracked and re-checked on the next assessment run."
    )

    doc.save(str(output_path))


def _add_title_page(doc: Document, assessment: Assessment, config: AssessmentConfig) -> None:
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(config.report.title)
    run.font.size = Pt(28)
    run.font.bold = True

    if config.report.company_name:
        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub.add_run(config.report.company_name).font.size = Pt(16)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"Generated {assessment.metadata.assessment_timestamp}\n"
        f"vhealth {assessment.metadata.app_version} · "
        f"rule engine {assessment.metadata.rule_engine_version}\n"
        f"Input: {assessment.metadata.input_filename}\n"
        f"SHA-256: {assessment.metadata.input_sha256}"
    ).font.size = Pt(10)


def _add_executive_summary(doc: Document, assessment: Assessment) -> None:
    counts: dict[Severity, int] = {}
    for finding in assessment.findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    table = doc.add_table(rows=1, cols=len(Severity))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, sev in enumerate(Severity):
        hdr[i].text = sev.value.upper()
    row = table.add_row().cells
    for i, sev in enumerate(Severity):
        row[i].text = str(counts.get(sev, 0))

    doc.add_paragraph(
        f"{len(assessment.hosts)} ESXi host(s) were assessed from this support bundle. "
        f"{len(assessment.findings)} finding(s) were raised."
    )


def _add_scope(doc: Document, assessment: Assessment) -> None:
    doc.add_paragraph(
        "This report was produced entirely offline from the customer-supplied diagnostic "
        "bundle below; no connection was made to any vCenter Server, ESXi host, or external "
        "service, and no customer data leaves this workstation."
    )
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light List Accent 1"
    for label, value in [
        ("Input file", assessment.metadata.input_filename),
        ("SHA-256", assessment.metadata.input_sha256),
        ("Hosts discovered", str(len(assessment.hosts))),
        ("Assessment schema", assessment.metadata.schema_version),
    ]:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value


def _add_hardware_status(doc: Document, assessment: Assessment) -> None:
    for host in assessment.hosts:
        doc.add_heading(host.hostname, level=3)
        table = doc.add_table(rows=0, cols=2)
        table.style = "Light List Accent 1"
        for label, value in [
            ("ESXi version", host.esxi_version or "unknown"),
            ("Build", host.esxi_build or "unknown"),
            ("Captured on", host.captured_on or "unknown"),
            ("Storage adapters", str(len(host.storage_adapters))),
            ("Storage devices", str(len(host.storage_devices))),
            ("Hardware sensors", str(len(host.sensors))),
        ]:
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = value


def _add_storage_components(doc: Document, assessment: Assessment) -> None:
    for host in assessment.hosts:
        doc.add_heading(f"{host.hostname} — storage adapters", level=3)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        for i, label in enumerate(["HBA", "Driver", "Description", "Link state"]):
            table.rows[0].cells[i].text = label
        for adapter in host.storage_adapters:
            cells = table.add_row().cells
            cells[0].text = adapter.device
            cells[1].text = adapter.driver or ""
            cells[2].text = adapter.description or ""
            cells[3].text = adapter.link_state or ""


def _add_findings(doc: Document, assessment: Assessment) -> None:
    findings = sorted(assessment.findings, key=lambda f: -f.severity.rank)
    if not findings:
        doc.add_paragraph("No findings were raised by the rule catalogue for this bundle.")
        return
    for finding in findings:
        heading = doc.add_paragraph()
        run = heading.add_run(f"[{finding.severity.value.upper()}] {finding.title}")
        run.bold = True
        run.font.color.rgb = _SEVERITY_COLOR[finding.severity]

        meta = f"{finding.rule_id}"
        if finding.affected_host:
            meta += f" · {finding.affected_host}"
        if finding.affected_object:
            meta += f" · {finding.affected_object}"
        meta_p = doc.add_paragraph()
        meta_p.add_run(meta).italic = True

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
