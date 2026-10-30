from synthetic_bundle import build_tgz, build_vcenter_zip

from vhealth.config import load_config
from vhealth.pipeline import run_assessment


def test_run_assessment_on_single_host_tgz(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz", smart_health="FAILED")
    config = load_config(None)
    assessment = run_assessment(bundle_path, tmp_path / "out", config)

    assert len(assessment.hosts) == 1
    assert assessment.metadata.input_sha256
    assert assessment.metadata.schema_version == "1.0.0"
    rule_ids = {f.rule_id for f in assessment.findings}
    assert "storage.smart_health_not_ok" in rule_ids


def test_run_assessment_on_multi_host_vcenter_zip(tmp_path):
    bundle_path = build_vcenter_zip(
        tmp_path / "vc.zip", hostnames=["esxi-a.example.test", "esxi-b.example.test"]
    )
    config = load_config(None)
    assessment = run_assessment(bundle_path, tmp_path / "out", config)

    assert len(assessment.hosts) == 2
    hostnames = {h.hostname for h in assessment.hosts}
    assert hostnames == {"esxi-a.example.test", "esxi-b.example.test"}


def test_run_assessment_is_deterministic_apart_from_timestamp(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz")
    config = load_config(None)

    a1 = run_assessment(bundle_path, tmp_path / "out1", config)
    a2 = run_assessment(bundle_path, tmp_path / "out2", config)

    dump1 = a1.model_dump(exclude={"metadata": {"assessment_timestamp"}})
    dump2 = a2.model_dump(exclude={"metadata": {"assessment_timestamp"}})
    assert dump1 == dump2


def test_disabled_rules_are_skipped(tmp_path):
    bundle_path = build_tgz(tmp_path / "host.tgz", smart_health="FAILED")
    config = load_config(None)
    object.__setattr__(config, "disabled_rules", ("storage.smart_health_not_ok",))

    assessment = run_assessment(bundle_path, tmp_path / "out", config)
    rule_ids = {f.rule_id for f in assessment.findings}
    assert "storage.smart_health_not_ok" not in rule_ids
