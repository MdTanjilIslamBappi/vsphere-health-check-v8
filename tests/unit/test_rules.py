from synthetic_bundle import build_host_dir

from vhealth.models.host import HostInfo
from vhealth.parsers import PARSER_MODULES
from vhealth.rules import evaluate_all, evaluate_all_fleet


def _assessed_host(tmp_path, **kwargs) -> HostInfo:
    host_dir = build_host_dir(tmp_path, **kwargs)
    host = HostInfo(hostname="placeholder", bundle_source=str(host_dir))
    for module in PARSER_MODULES:
        host.parse_warnings.extend(module.parse(host_dir, host))
    return host


def test_healthy_synthetic_host_raises_no_findings(tmp_path):
    host = _assessed_host(tmp_path)
    findings = evaluate_all([host])
    assert findings == []


def test_smart_failure_raises_finding(tmp_path):
    host = _assessed_host(tmp_path, smart_health="FAILED")
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "storage.smart_health_not_ok" in rule_ids


def test_asserted_sensor_raises_finding(tmp_path):
    host = _assessed_host(tmp_path, sensor_asserted=True)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.ipmi_sensor_asserted" in rule_ids


def test_pdl_log_signal_raises_critical_finding(tmp_path):
    host = _assessed_host(tmp_path, include_pdl_warning=True)
    findings = evaluate_all([host])
    pdl_findings = [f for f in findings if f.rule_id == "storage.pdl_detected"]
    assert len(pdl_findings) == 1
    assert pdl_findings[0].severity.value == "critical"


def test_old_pdl_warning_outside_quarter_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, include_old_pdl_warning=True)
    findings = evaluate_all([host])
    assert "storage.pdl_detected" not in {f.rule_id for f in findings}


def test_recent_pdl_finding_notes_excluded_older_occurrences(tmp_path):
    host = _assessed_host(tmp_path, include_pdl_warning=True, include_old_pdl_warning=True)
    findings = evaluate_all([host])
    pdl_finding = next(f for f in findings if f.rule_id == "storage.pdl_detected")
    assert "1 additional older occurrence" in pdl_finding.limitations


def test_findings_carry_remediation_and_limitations(tmp_path):
    host = _assessed_host(tmp_path, smart_health="FAILED")
    findings = evaluate_all([host])
    finding = next(f for f in findings if f.rule_id == "storage.smart_health_not_ok")
    assert finding.remediation
    assert finding.limitations
    assert finding.affected_host == host.hostname


def test_minimal_capture_host_raises_coverage_finding(tmp_path):
    host = _assessed_host(tmp_path, minimal_capture=True)
    findings = evaluate_all([host])
    coverage_findings = [f for f in findings if f.rule_id == "coverage.limited_diagnostic_data"]
    assert len(coverage_findings) == 1
    assert coverage_findings[0].severity.value == "low"
    assert len(coverage_findings[0].evidence) == 6


def test_disabled_rules_are_excluded(tmp_path):
    host = _assessed_host(tmp_path, smart_health="FAILED")
    findings = evaluate_all([host], disabled_rules=("storage.smart_health_not_ok",))
    assert "storage.smart_health_not_ok" not in {f.rule_id for f in findings}


def test_single_host_raises_no_cpu_mismatch_finding(tmp_path):
    host = _assessed_host(tmp_path)
    findings = evaluate_all_fleet([host])
    assert findings == []


def test_mismatched_cpu_models_raise_fleet_finding():
    host_a = HostInfo(hostname="host-a", bundle_source="a", cpu_model="Intel Xeon Gold 6258R")
    host_b = HostInfo(hostname="host-b", bundle_source="b", cpu_model="Intel Xeon Gold 6430")
    findings = evaluate_all_fleet([host_a, host_b])
    assert len(findings) == 1
    assert findings[0].rule_id == "fleet.cpu_model_mismatch"
    assert findings[0].severity.value == "medium"


def test_matching_cpu_models_raise_no_fleet_finding():
    host_a = HostInfo(hostname="host-a", bundle_source="a", cpu_model="Intel Xeon Gold 6258R")
    host_b = HostInfo(hostname="host-b", bundle_source="b", cpu_model="Intel Xeon Gold 6258R")
    assert evaluate_all_fleet([host_a, host_b]) == []


def test_fleet_disabled_rules_are_excluded():
    host_a = HostInfo(hostname="host-a", bundle_source="a", cpu_model="Intel Xeon Gold 6258R")
    host_b = HostInfo(hostname="host-b", bundle_source="b", cpu_model="Intel Xeon Gold 6430")
    findings = evaluate_all_fleet(
        [host_a, host_b], disabled_rules=("fleet.cpu_model_mismatch",)
    )
    assert findings == []
