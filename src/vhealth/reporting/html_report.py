from __future__ import annotations

from importlib import resources
from pathlib import Path

from jinja2 import Environment

from vhealth.config import AssessmentConfig
from vhealth.models.assessment import Assessment
from vhealth.reporting.authorship import ReportAuthorship
from vhealth.rules import ALL_RULES

VERSION = "1.0.0"

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
        rule_count=len(ALL_RULES),
    )
    output_path.write_text(html, encoding="utf-8")
