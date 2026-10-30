from __future__ import annotations

from importlib import resources
from pathlib import Path

from jinja2 import Environment

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.reporting import summary
from vhealth.reporting.authorship import ReportAuthorship

VERSION = "3.0.0"

_TEMPLATE_PATH = "templates/report.html.j2"


def write_html_report(
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

    severity_counts: dict[str, int] = {}
    for finding in assessment.findings:
        severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1

    html = template.render(
        assessment=assessment,
        config=config,
        authorship=authorship or ReportAuthorship(),
        hosts=assessment.hosts,
        severity_counts=severity_counts,
        executive_summary=summary.executive_summary_text(assessment),
        scope_items=summary.SCOPE_ITEMS,
        hardware_status_grid=summary.hardware_status_grid(assessment),
        component_status_rows=summary.component_status_rows(assessment),
        key_findings=summary.key_findings_at_a_glance(assessment),
        host_inventory_rows=summary.host_inventory_rows(assessment),
        detailed_observations=summary.detailed_observations(assessment),
        recommendation_groups=summary.recommendation_groups(assessment),
    )
    output_path.write_text(html, encoding="utf-8")
