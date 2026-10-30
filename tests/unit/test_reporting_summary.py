from vhealth.models.assessment import Assessment, AssessmentMetadata
from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.reporting import summary


def _metadata(**overrides) -> AssessmentMetadata:
    defaults = dict(
        app_version="0.1.0",
        rule_engine_version="1.2.0",
        input_filename="bundle.tgz",
        input_sha256="deadbeef",
        assessment_timestamp="2026-01-01T00:00:00+00:00",
        config_fingerprint="fingerprint",
    )
    defaults.update(overrides)
    return AssessmentMetadata(**defaults)


def test_component_status_rows_marks_unassessed_vcenter_sections():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["vCenter Server"].status == summary.NOT_ASSESSED
    assert rows["EVC Mode"].status == summary.NOT_ASSESSED
    assert rows["Datastores"].status == summary.NOT_ASSESSED
    assert rows["Virtual Machines"].status == summary.NOT_ASSESSED


def test_component_status_rows_flags_attention_for_high_severity_finding():
    host = HostInfo(hostname="h1", bundle_source="h1", esxi_version="8.0.3")
    finding = Finding(
        rule_id="storage.device_not_on",
        title="Storage device is not in the 'on' state",
        severity=Severity.HIGH,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Storage & Hardware Findings"].status == "Attention Needed"
    assert rows["Overall"].status == "Attention Needed"


def test_host_inventory_rows_use_unknown_for_missing_fields():
    host = HostInfo(hostname="h1", bundle_source="h1")
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = summary.host_inventory_rows(assessment)
    assert rows == [
        summary.HostInventoryRow(
            index=1, hostname="h1", management_ip="unknown",
            server_model="unknown", cpu_model="unknown",
        )
    ]


def test_host_inventory_rows_combine_manufacturer_and_model():
    host = HostInfo(
        hostname="h1", bundle_source="h1",
        server_manufacturer="Dell Inc.", server_model="PowerEdge R740xd",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = summary.host_inventory_rows(assessment)
    assert rows[0].server_model == "Dell Inc. PowerEdge R740xd"


def test_recommendation_groups_are_sorted_by_severity_and_deduplicate_hosts():
    findings = [
        Finding(
            rule_id="storage.device_not_on", title="Device not on", severity=Severity.HIGH,
            summary="...", affected_host="h1", remediation="Check paths.",
        ),
        Finding(
            rule_id="storage.device_not_on", title="Device not on", severity=Severity.HIGH,
            summary="...", affected_host="h1", remediation="Check paths.",
        ),
        Finding(
            rule_id="coverage.limited_diagnostic_data", title="Limited data",
            severity=Severity.LOW, summary="...", affected_host="h2",
        ),
    ]
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=findings)
    groups = summary.recommendation_groups(assessment)
    assert [g.severity for g in groups] == ["high", "low"]
    assert groups[0].affected == ["h1"]


def test_executive_summary_text_reports_no_findings_honestly():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    text = summary.executive_summary_text(assessment)
    assert "No findings were raised" in text


def test_key_findings_at_a_glance_notes_not_assessed_items():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    items = summary.key_findings_at_a_glance(assessment)
    assert any("not assessed" in item for item in items)


def test_hardware_status_grid_marks_management_connection_not_assessed():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    grid = summary.hardware_status_grid(assessment)
    assert grid.management_connection == summary.NOT_ASSESSED


def test_detailed_observations_mentions_quarterly_window():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    items = summary.detailed_observations(assessment)
    assert any("90 days" in item for item in items)
