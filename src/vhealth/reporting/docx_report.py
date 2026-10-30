from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, RGBColor

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.models.findings import Severity
from vhealth.reporting import summary
from vhealth.reporting.authorship import ReportAuthorship

VERSION = "3.1.0"

_STATUS_COLOR = {
    "Healthy": RGBColor(0x1E, 0x7E, 0x34),
    "Informational": RGBColor(0x5B, 0x8D, 0xEF),
    "Advisory": RGBColor(0xC7, 0x7C, 0x00),
    "Attention Needed": RGBColor(0xB3, 0x00, 0x00),
    summary.NOT_ASSESSED: RGBColor(0x6C, 0x75, 0x7D),
}

# Kept in sync with the doc.add_heading(...) calls in write_docx_report
# below -- used only as the Table of Contents field's fallback display
# text (see _add_table_of_contents).
_SECTION_HEADINGS = (
    "1. Executive Summary",
    "2. Scope of Health Check",
    "3. System Status",
    "3.1 Current Hardware Status",
    "3.2 Current State Analysis of VMware Components",
    "3.3 Current State Analysis of ESXi Hosts",
    "3.4 Virtual Machine Inventory",
    "3.5 Recommendation",
)


def write_docx_report(
    assessment: Assessment,
    config: AssessmentConfig,
    output_path: Path,
    authorship: ReportAuthorship | None = None,
) -> None:
    authorship = authorship or ReportAuthorship()
    doc = Document()
    _force_field_update_on_open(doc)

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

    doc.add_heading("3.4 Virtual Machine Inventory", level=2)
    _add_virtual_machine_inventory_table(doc, assessment)

    doc.add_heading("3.5 Recommendation", level=2)
    _add_recommendations(doc, assessment)

    doc.add_paragraph()
    note = doc.add_paragraph()
    note.add_run(
        "A separate detailed findings log accompanies this report, with the full "
        "evidence-level breakdown behind every item above."
    ).italic = True

    doc.save(str(output_path))


def _force_field_update_on_open(doc: Document) -> None:
    """Make Word recompute fields (the Table of Contents in particular) as
    soon as the document is opened, instead of requiring a manual
    right-click -> Update Field. Nothing in this pipeline lays out pages,
    so real page numbers can only come from Word's own layout engine once
    it opens the file; see _add_table_of_contents for the honest fallback
    shown in viewers that don't run field updates at all.
    """
    settings = doc.settings.element
    update_fields = OxmlElement("w:updateFields")
    update_fields.set(qn("w:val"), "true")
    compat = settings.find(qn("w:compat"))
    if compat is not None:
        compat.addprevious(update_fields)
    else:
        settings.append(update_fields)


def _add_anchored_picture(
    paragraph,
    image_path: str,
    *,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    behind_doc: bool,
    relative_height: int,
    name: str,
    position_h_relative: str = "column",
    position_v_relative: str = "paragraph",
) -> None:
    """Add a floating (anchored) picture to ``paragraph`` at a fixed
    position/size, matching how a corporate cover-page template typically
    places its background graphic and logos (as opposed to an inline
    picture that flows with the text).
    """
    run = paragraph.add_run()
    run.add_picture(image_path, width=Emu(cx_emu), height=Emu(cy_emu))
    drawing = run._r.find(qn("w:drawing"))
    inline = drawing.find(qn("wp:inline"))
    graphic = inline.find(qn("a:graphic"))
    doc_pr = inline.find(qn("wp:docPr"))
    cnv_frame_pr = inline.find(qn("wp:cNvGraphicFramePr"))
    inline.remove(graphic)
    drawing.remove(inline)

    anchor = OxmlElement("wp:anchor")
    for attr, value in {
        "distT": "0",
        "distB": "0",
        "distL": "114300",
        "distR": "114300",
        "simplePos": "0",
        "relativeHeight": str(relative_height),
        "behindDoc": "1" if behind_doc else "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(attr, value)

    simple_pos = OxmlElement("wp:simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    anchor.append(simple_pos)

    position_h = OxmlElement("wp:positionH")
    position_h.set("relativeFrom", position_h_relative)
    pos_offset_h = OxmlElement("wp:posOffset")
    pos_offset_h.text = str(x_emu)
    position_h.append(pos_offset_h)
    anchor.append(position_h)

    position_v = OxmlElement("wp:positionV")
    position_v.set("relativeFrom", position_v_relative)
    pos_offset_v = OxmlElement("wp:posOffset")
    pos_offset_v.text = str(y_emu)
    position_v.append(pos_offset_v)
    anchor.append(position_v)

    extent = OxmlElement("wp:extent")
    extent.set("cx", str(cx_emu))
    extent.set("cy", str(cy_emu))
    anchor.append(extent)

    anchor.append(OxmlElement("wp:wrapNone"))

    doc_pr.set("name", name)
    anchor.append(doc_pr)
    if cnv_frame_pr is not None:
        anchor.append(cnv_frame_pr)
    anchor.append(graphic)

    drawing.append(anchor)


# Fixed cover-page layout for the three optional branding images, matching
# a specific customer-report convention (reverse-engineered from a shared
# reference template). Positions/sizes are generic geometry, not
# proprietary content -- the image *files* are never part of this repo
# (see ReportConfig.cover_background_image and friends).
_COVER_BACKGROUND_ANCHOR = dict(
    x_emu=-908050, y_emu=419100, cx_emu=7846060, cy_emu=7172960,
    behind_doc=True, relative_height=251658241, name="Cover background",
    position_h_relative="column", position_v_relative="paragraph",
)
_PREPARER_LOGO_ANCHOR = dict(
    x_emu=-749300, y_emu=-647700, cx_emu=2658187, cy_emu=806450,
    behind_doc=False, relative_height=251658243, name="Preparer logo",
    position_h_relative="column", position_v_relative="paragraph",
)
_CUSTOMER_LOGO_ANCHOR = dict(
    x_emu=5740400, y_emu=-698500, cx_emu=774700, cy_emu=720895,
    behind_doc=False, relative_height=251658240, name="Customer logo",
    position_h_relative="margin", position_v_relative="paragraph",
)


def _add_cover_branding(doc: Document, config: AssessmentConfig) -> None:
    """Add the cover-page branding images, if configured. Silently does
    nothing for any image that isn't set or doesn't exist on disk, so a
    missing/misconfigured path never breaks report generation -- the
    plain-text cover page (no images) is this tool's default.
    """
    images = [
        (config.report.cover_background_image, _COVER_BACKGROUND_ANCHOR),
        (config.report.preparer_logo_image, _PREPARER_LOGO_ANCHOR),
        (config.report.customer_logo_image, _CUSTOMER_LOGO_ANCHOR),
    ]
    if not any(path for path, _ in images):
        return

    anchor_paragraph = doc.paragraphs[0] if doc.paragraphs else doc.add_paragraph()
    for path, anchor_kwargs in images:
        if path and Path(path).is_file():
            _add_anchored_picture(anchor_paragraph, path, **anchor_kwargs)


def _add_title_page(
    doc: Document, assessment: Assessment, config: AssessmentConfig, authorship: ReportAuthorship
) -> None:
    _add_cover_branding(doc, config)

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
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for i, label in enumerate(["Date", "Rev.", "Author", "Description", "Reviewers"]):
        table.rows[0].cells[i].text = label
    row = table.add_row().cells
    row[0].text = assessment.metadata.assessment_timestamp.split("T")[0]
    row[1].text = authorship.revision
    row[2].text = authorship.author or authorship.engineer_name or ""
    row[3].text = authorship.description
    row[4].text = authorship.verifier or ""


def _add_table_of_contents(doc: Document) -> None:
    """Insert a real Word TOC field (not a static table), scoped to
    heading levels 1-3. Word recomputes it with real page numbers as soon
    as the document is opened (see _force_field_update_on_open) -- the
    text below is only the fallback a viewer shows if it doesn't run
    field updates at all, so it lists the real section titles rather
    than a "right-click to update" placeholder, but it cannot include
    page numbers since nothing in this pipeline lays out pages itself.
    """
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
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_separate)
    for i, heading_text in enumerate(_SECTION_HEADINGS):
        if i:
            run._r.append(OxmlElement("w:br"))
        fld_text = OxmlElement("w:t")
        fld_text.set(qn("xml:space"), "preserve")
        fld_text.text = heading_text
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
    for item in summary.scope_items(assessment):
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph(
        "This assessment was performed entirely offline against the customer-supplied "
        "diagnostic bundle below; no connection was made to vCenter or any ESXi host."
    )
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light List Accent 1"
    rows_for_table = [
        ("Input file", assessment.metadata.input_filename),
        ("Hosts assessed", str(len(assessment.hosts))),
    ]
    if assessment.vcenter is not None:
        rows_for_table.append(
            ("vCenter appliance assessed", str(assessment.vcenter.hostname))
        )
    for label, value in rows_for_table:
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


def _add_virtual_machine_inventory_table(doc: Document, assessment: Assessment) -> None:
    rows = summary.virtual_machine_inventory_rows(assessment)
    if not rows:
        doc.add_paragraph(
            "Not assessed; no running-VM data (localcli vm process list) was found "
            "in this bundle."
        )
        return
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    headers = ["S.No", "VM Name", "Host", "Datastore", "UUID"]
    for i, label in enumerate(headers):
        table.rows[0].cells[i].text = label
    for row_data in rows:
        cells = table.add_row().cells
        cells[0].text = str(row_data.index)
        cells[1].text = row_data.name
        cells[2].text = row_data.host
        cells[3].text = row_data.datastore
        cells[4].text = row_data.uuid
    note = doc.add_paragraph()
    note.add_run(
        "Powered-on VMs only, as reported by each host itself at capture time; a support "
        "bundle has no record of powered-off VMs or resource-utilization history -- that "
        "lives only in vCenter's own inventory database."
    ).italic = True


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
        p.add_run("Category: ").bold = True
        p.add_run(group.category)

        p = doc.add_paragraph()
        p.add_run("Severity: ").bold = True
        p.add_run(group.severity.upper())

        p = doc.add_paragraph()
        p.add_run("Affected: ").bold = True
        p.add_run(", ".join(group.affected))

        p = doc.add_paragraph()
        p.add_run("Why it matters: ").bold = True
        p.add_run(group.limitations or "See the companion findings log for detail.")

        p = doc.add_paragraph()
        p.add_run("Where to check / action: ").bold = True
        p.add_run(group.action)

        if group.evidence:
            p = doc.add_paragraph()
            p.add_run("Evidence:").bold = True
            table = doc.add_table(rows=0, cols=1)
            table.style = "Light Grid Accent 1"
            for line in group.evidence:
                table.add_row().cells[0].text = line
