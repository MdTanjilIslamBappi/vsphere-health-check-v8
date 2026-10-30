from __future__ import annotations

from importlib import resources
from pathlib import Path

from jinja2 import Environment

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.reporting import summary
from vhealth.reporting.authorship import ReportAuthorship
from vhealth.rules import ALL_FLEET_RULES, ALL_RULES

VERSION = "2.0.0"

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
        findings=sorted(assessment.findings, key=lambda f: -f.severity.rank),
        severity_counts=severity_counts,
        rule_count=len(ALL_RULES) + len(ALL_FLEET_RULES),
        executive_summary=summary.executive_summary_text(assessment),
        scope_checked=summary.SCOPE_CHECKED,
        scope_not_assessed=summary.SCOPE_NOT_ASSESSED,
        hardware_status_rows=summary.hardware_status_rows(assessment),
        component_status_rows=summary.component_status_rows(assessment),
        host_inventory_rows=summary.host_inventory_rows(assessment),
        recommendation_groups=summary.recommendation_groups(assessment),
        not_assessed_status=summary.NOT_ASSESSED,
        cluster_hosts=[h for h in assessment.hosts if h.cluster_id],
    )
    output_path.write_text(html, encoding="utf-8")
