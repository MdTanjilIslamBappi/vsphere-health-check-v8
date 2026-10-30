from synthetic_bundle import build_tgz, build_vcenter_zip, build_vcenter_zip_with_vcsa

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


def test_run_assessment_parses_vcenter_bundle_member(tmp_path):
    bundle_path = build_vcenter_zip_with_vcsa(
        tmp_path / "vc.zip",
        hostnames=["esxi-a.example.test"],
        vcls_membership=False,
        cluster_name="NOTHING",
    )
    config = load_config(None)
    assessment = run_assessment(bundle_path, tmp_path / "out", config)

    # The vCenter member must not count as a host.
    assert len(assessment.hosts) == 1
    assert assessment.hosts[0].hostname == "esxi-a.example.test"

    vcenter = assessment.vcenter
    assert vcenter is not None
    print("DEBUG vcenter:", vcenter.hostname, vcenter.bundle_source, vcenter.parse_warnings)
    assert vcenter.hostname == "vcsa.example.test"
    assert vcenter.vc_version == "8.0.3.00900"

    rule_ids = {f.rule_id for f in assessment.findings}
    assert "vcenter.appliance_disk_usage" in rule_ids
    assert "vcenter.optional_service_stopped" in rule_ids

    # Evidence manifest covers the vCenter evidence files.
    paths = {e.path for e in assessment.metadata.evidence_manifest}
    assert any(p.startswith("vCenter/vcsa.example.test/") for p in paths)


def test_run_assessment_resolves_cluster_names_from_vcenter(tmp_path):
    bundle_path = build_vcenter_zip_with_vcsa(
        tmp_path / "vc.zip",
        hostnames=["esxi-a.example.test"],
        host_cluster_id="1da37019-edc3-4f56-8107-37b397523e5b:domain-c1001",
        cluster_name="EAMSC2",
        cluster_moref="domain-c1001",
    )
    config = load_config(None)
    assessment = run_assessment(bundle_path, tmp_path / "out", config)

    assert assessment.vcenter is not None
    assert assessment.vcenter.cluster_names == {"domain-c1001": "EAMSC2"}
    host = assessment.hosts[0]
    assert host.cluster_name == "EAMSC2"


def test_run_assessment_resolves_cluster_name_from_vcls_membership_without_host_cluster_id(
    tmp_path,
):
    """A host that never reports its own cluster ID (clusterAdmin output

    missing/stale is common in real bundles) must still resolve its
    cluster name, as long as the vCenter bundle's vCLS membership log lists
    that hostname under a cluster moref vhealth can name.
    """
    bundle_path = build_vcenter_zip_with_vcsa(
        tmp_path / "vc.zip",
        hostnames=["esx01-synthetic.example.test"],
        cluster_name="EAMSC2",
        cluster_moref="domain-c1001",
    )
    config = load_config(None)
    assessment = run_assessment(bundle_path, tmp_path / "out", config)

    host = assessment.hosts[0]
    # The synthetic host fixture's own (unrelated) default cluster ID, which
    # does not match any vCenter-reported moref -- the resolution must fall
    # through to the hostname-based vCLS membership match instead.
    assert host.cluster_id == "cluster-synthetic-01"
    assert host.cluster_name == "EAMSC2"
