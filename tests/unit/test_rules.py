from synthetic_bundle import build_host_dir

from vhealth.models.host import HostInfo
from vhealth.parsers import PARSER_MODULES
from vhealth.rules import evaluate_all


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


def test_findings_carry_remediation_and_limitations(tmp_path):
    host = _assessed_host(tmp_path, smart_health="FAILED")
    findings = evaluate_all([host])
    finding = next(f for f in findings if f.rule_id == "storage.smart_health_not_ok")
    assert finding.remediation
    assert finding.limitations
    assert finding.affected_host == host.hostname
