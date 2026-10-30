from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.models.findings import Severity
from vhealth.reporting import summary
from vhealth.reporting.authorship import ReportAuthorship

VERSION = "3.0.0"

_STATUS_COLOR = {
    "Healthy": RGBColor(0x1E, 0x7E, 0x34),
    "Informational": RGBColor(0x5B, 0x8D, 0xEF),
    "Advisory": RGBColor(0xC7, 0x7C, 0x00),
    "Attention Needed": RGBColor(0xB3, 0x00, 0x00),
    summary.NOT_ASSESSED: RGBColor(0x6C, 0x75, 0x7D),
}


def write_docx_report(
    assessment: Assessment,
    config: AssessmentConfig,
    output_path: Path,
    authorship: ReportAuthorship | None = None,
) -> None:
    authorship = authorship or ReportAuthorship()
    doc = Document()

    _add_title_page(doc, assessment, config, authorship)
    doc.add_page_break()

    _add_version_history(doc, assessment, authorship)
    doc.add_page_break()

    _add_table_of_contents(doc)
    doc.add_page_break()

    doc.add_heading("1. Executive Summary", level=1)
    doc.add_paragraph(summary.executive_summary_text(assessment))
    _add_severity_counts(doc, assessment)

    doc.add_heading("2. Scope of Health Check", level=1)
    _add_scope(doc, assessment)

    doc.add_heading("3. System Status", level=1)

    doc.add_heading("3.1 Current Hardware Status", level=2)
    _add_hardware_status_grid(doc, assessment)

    doc.add_heading("3.2 Current State Analysis of VMware Components", level=2)
    _add_component_status_table(doc, assessment)
    doc.add_paragraph("Key Findings at a Glance").runs[0].bold = True
    for item in summary.key_findings_at_a_glance(assessment):
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("3.3 Current State Analysis of ESXi Hosts", level=2)
    _add_host_inventory_table(doc, assessment)
    doc.add_paragraph("Detailed Observations").runs[0].bold = True
    for item in summary.detailed_observations(assessment):
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("3.4 Recommendation", level=2)
    _add_recommendations(doc, assessment)

    doc.add_paragraph()
    note = doc.add_paragraph()
    note.add_run(
        "A separate detailed findings log accompanies this report, with the full "
        "evidence-level breakdown behind every item above."
    ).italic = True

    doc.save(str(output_path))


def _add_title_page(
    doc: Document, assessment: Assessment, config: AssessmentConfig, authorship: ReportAuthorship
) -> None:
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
    meta.add_run(f"Generated {assessment.metadata.assessment_timestamp}").font.size = Pt(10)

    if not authorship.is_empty:
        table = doc.add_table(rows=0, cols=2)
        table.style = "Light List Accent 1"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for label, value in [
            ("Engineer", authorship.engineer_name),
            ("Author", authorship.author),
            ("Verified by", authorship.verifier),
        ]:
            if not value:
                continue
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = value


def _add_version_history(
    doc: Document, assessment: Assessment, authorship: ReportAuthorship
) -> None:
    doc.add_heading("Version History", level=1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    for i, label in enumerate(["Date", "Rev.", "Author", "Description"]):
        table.rows[0].cells[i].text = label
    row = table.add_row().cells
    row[0].text = assessment.metadata.assessment_timestamp.split("T")[0]
    row[1].text = authorship.revision
    row[2].text = authorship.author or authorship.engineer_name or ""
    row[3].text = authorship.description


def _add_table_of_contents(doc: Document) -> None:
    doc.add_heading("Contents", level=1)
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")
    fld_text = OxmlElement("w:t")
    fld_text.text = "Right-click here and choose Update Field to populate the table of contents."
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_separate)
    run._r.append(fld_text)
    run._r.append(fld_end)


def _add_severity_counts(doc: Document, assessment: Assessment) -> None:
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


def _add_scope(doc: Document, assessment: Assessment) -> None:
    doc.add_paragraph("The following was reviewed during this health check assessment:")
    for item in summary.SCOPE_ITEMS:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph(
        "This assessment was performed entirely offline against the customer-supplied "
        "diagnostic bundle below; no connection was made to vCenter or any ESXi host."
    )
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light List Accent 1"
    for label, value in [
        ("Input file", assessment.metadata.input_filename),
        ("Hosts assessed", str(len(assessment.hosts))),
    ]:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value

    if assessment.metadata.processing_warnings:
        doc.add_paragraph(
            "Some processing warnings were recorded during this assessment; see the "
            "detailed findings log for the full list."
        ).runs[0].italic = True


def _status_cell(cells, index: int, status: str) -> None:
    cells[index].text = status
    run = cells[index].paragraphs[0].runs[0]
    run.bold = True
    color = _STATUS_COLOR.get(status)
    if color:
        run.font.color.rgb = color


def _add_hardware_status_grid(doc: Document, assessment: Assessment) -> None:
    grid = summary.hardware_status_grid(assessment)
    table = doc.add_table(rows=3, cols=4)
    table.style = "Light Grid Accent 1"

    table.rows[0].cells[0].text = "HW / Disk"
    _status_cell(table.rows[0].cells, 1, grid.hw_disk)
    table.rows[0].cells[2].text = "Management Connection Status"
    _status_cell(table.rows[0].cells, 3, grid.management_connection)

    table.rows[1].cells[0].text = "Health"
    _status_cell(table.rows[1].cells, 1, grid.health)
    table.rows[1].cells[2].text = "Power"
    _status_cell(table.rows[1].cells, 3, grid.power)

    table.rows[2].cells[0].text = "Observations"
    obs_cell = table.rows[2].cells[1]
    obs_cell.merge(table.rows[2].cells[3])
    obs_cell.text = grid.observations


def _add_component_status_table(doc: Document, assessment: Assessment) -> None:
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    for i, label in enumerate(["Component", "Status", "Remarks"]):
        table.rows[0].cells[i].text = label
    for row_data in summary.component_status_rows(assessment):
        cells = table.add_row().cells
        cells[0].text = row_data.component
        _status_cell(cells, 1, row_data.status)
        cells[2].text = row_data.remarks


def _add_host_inventory_table(doc: Document, assessment: Assessment) -> None:
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    headers = ["S.No", "Server Name", "Management IP", "Server Model", "CPU Model"]
    for i, label in enumerate(headers):
        table.rows[0].cells[i].text = label
    for row_data in summary.host_inventory_rows(assessment):
        cells = table.add_row().cells
        cells[0].text = str(row_data.index)
        cells[1].text = row_data.hostname
        cells[2].text = row_data.management_ip
        cells[3].text = row_data.server_model
        cells[4].text = row_data.cpu_model


def _add_recommendations(doc: Document, assessment: Assessment) -> None:
    groups = summary.recommendation_groups(assessment)
    if not groups:
        doc.add_paragraph("No findings were raised, so there are no recommendations to track.")
        return
    for group in groups:
        heading = doc.add_paragraph()
        run = heading.add_run(group.title)
        run.bold = True

        p = doc.add_paragraph()
        p.add_run("Severity: ").bold = True
        p.add_run(group.severity.upper())

        p = doc.add_paragraph()
        p.add_run("Affected: ").bold = True
        p.add_run(", ".join(group.affected))

        p = doc.add_paragraph()
        p.add_run("Action: ").bold = True
        p.add_run(group.action)
