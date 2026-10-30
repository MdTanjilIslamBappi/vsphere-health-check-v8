from __future__ import annotations

from synthetic_bundle import build_host_dir, build_vcsa_dir

from vhealth.discovery import bundle as discovery
from vhealth.models.assessment import Assessment, AssessmentMetadata
from vhealth.models.host import HostInfo
from vhealth.models.vcenter import VCenterInfo
from vhealth.parsers import vcenter as vcenter_parser
from vhealth.reporting import summary
from vhealth.rules.vcenter_rules import evaluate_all_vcenter


def _parse_vcsa(tmp_path, **kwargs) -> VCenterInfo:
    bundle_dir = build_vcsa_dir(tmp_path, **kwargs)
    info = VCenterInfo(hostname="vcsa", bundle_source=bundle_dir.name)
    info.parse_warnings.extend(vcenter_parser.parse(bundle_dir, info))
    return info


def _metadata() -> AssessmentMetadata:
    return AssessmentMetadata(
        app_version="0.1.0",
        rule_engine_version="1.3.0",
        input_filename="bundle.zip",
        input_sha256="deadbeef",
        assessment_timestamp="2026-01-01T00:00:00+00:00",
        config_fingerprint="fingerprint",
    )


def _assessment(vcenter: VCenterInfo | None, hosts=()) -> Assessment:
    return Assessment(metadata=_metadata(), hosts=list(hosts), findings=[], vcenter=vcenter)


# --- discovery -------------------------------------------------------------


def test_host_discovery_excludes_vcenter_bundle(tmp_path):
    build_vcsa_dir(tmp_path)
    build_host_dir(tmp_path, hostname="esxi-a.example.test")

    refs = discovery.find_host_bundles(tmp_path)
    assert len(refs) == 1
    assert refs[0].root.name.startswith("esx-")

    vc_refs = discovery.find_vcenter_bundles(tmp_path)
    assert len(vc_refs) == 1
    assert vc_refs[0].root.name.startswith("vc-vcsa.example.test")


def test_vcenter_bundle_is_not_a_host_bundle(tmp_path):
    build_vcsa_dir(tmp_path)
    assert discovery.find_host_bundles(tmp_path) == []
    assert len(discovery.find_vcenter_bundles(tmp_path)) == 1


# --- vCenter parser ---------------------------------------------------------


def test_parse_vcsa_bundle_identity_and_services(tmp_path):
    info = _parse_vcsa(tmp_path)
    assert info.hostname == "vcsa.example.test"
    assert info.hostname_source == "uname"
    assert info.captured_on == "2026-01-15 11:00:00.000000"
    assert info.vc_version == "8.0.3.00900"
    assert info.vc_build == "12345678"
    assert "vmware-vpxd" in info.services_running
    assert set(info.services_stopped) == {"vmcam", "vmonapi", "vmware-imagebuilder", "vmware-vcha"}
    assert info.parse_warnings == []


def test_parse_vcsa_bundle_disks_ignore_transients(tmp_path):
    info = _parse_vcsa(tmp_path)
    mounts = {d.mount: d.percent_used for d in info.appliance_disks}
    assert mounts == {"/": 36, "/storage/db": 92, "/storage/archive": 95}


def test_parse_vcsa_bundle_cluster_inventory(tmp_path):
    info = _parse_vcsa(tmp_path)
    assert info.cluster_names == {"domain-c1001": "EAMSC2"}
    assert info.cluster_members == {
        "domain-c1001": [
            "esx01.example.test",
            "esx02.example.test",
        ]
    }


def test_parse_vcsa_without_cluster_evidence_returns_warnings(tmp_path):
    bare = build_vcsa_dir(tmp_path, cluster_name="NOSUCHNAME", vcls_membership=False)
    (bare / "var" / "log" / "vmware" / "vpxd" / "vpxd-2508.log").unlink()
    info = VCenterInfo(hostname="vcsa", bundle_source=bare.name)
    warnings = vcenter_parser.parse(bare, info)
    assert info.cluster_names == {}
    assert any("cluster inventory" in w for w in warnings)


# --- rules -------------------------------------------------------------------


def test_core_stopped_service_is_high(tmp_path):
    info = _parse_vcsa(tmp_path)
    info.services_stopped.append("vmware-vpxd")
    findings = [
        f for f in evaluate_all_vcenter(info) if f.rule_id == "vcenter.core_service_stopped"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "high"
    assert "vmware-vpxd" in findings[0].summary


def test_optional_stopped_services_are_informational(tmp_path):
    info = _parse_vcsa(tmp_path)
    findings = [
        f
        for f in evaluate_all_vcenter(info)
        if f.rule_id == "vcenter.optional_service_stopped"
    ]
    assert len(findings) == 1
    assert findings[0].severity.value == "info"
    assert "vmware-vcha" in findings[0].summary


def test_appliance_disk_thresholds(tmp_path):
    info = _parse_vcsa(tmp_path)
    findings = {
        f.affected_object: f
        for f in evaluate_all_vcenter(info)
        if f.rule_id == "vcenter.appliance_disk_usage"
    }
    # /storage/db at 92% -> medium; /storage/archive at 95% -> high
    assert findings["/storage/db"].severity.value == "medium"
    assert findings["/storage/archive"].severity.value == "high"
    assert "/" not in findings and "/dev" not in findings


# --- summary integration ------------------------------------------------------


def test_scope_items_change_with_vcenter_bundle():
    host_only = summary.scope_items(_assessment(None))
    assert any("EVC mode configuration -- not assessed" in s for s in host_only)

    vcenter = VCenterInfo(hostname="vcsa01.example.test", bundle_source="vc-1")
    with_vcenter = summary.scope_items(_assessment(vcenter))
    assert any("vCenter Server appliance status" in s for s in with_vcenter)
    assert any("Cluster inventory" in s for s in with_vcenter)


def test_cluster_status_row_uses_resolved_names():
    vcenter = VCenterInfo(
        hostname="vcsa", bundle_source="x", cluster_names={"domain-c1001": "EAMSC2"}
    )
    host = HostInfo(
        hostname="esx01.example.test",
        bundle_source="esx-1",
        cluster_id="1da37019-edc3-4f56-8107-37b397523e5b:domain-c1001",
        cluster_name="EAMSC2",
    )
    standalone = HostInfo(hostname="esx02.example.test", bundle_source="esx-2")
    assessment = _assessment(vcenter, hosts=[host, standalone])
    rows = {r.component: r for r in summary.component_status_rows(assessment)}
    cluster_row = rows["Cluster Status"]
    assert "EAMSC2 (domain-c1001)" in cluster_row.remarks
    assert "1 of 2 host(s) report no cluster membership" in cluster_row.remarks
    assert cluster_row.status == "Informational"


def test_vcenter_server_row_reports_version_and_service_counts():
    vcenter = VCenterInfo(
        hostname="vcsa01.example.test",
        bundle_source="vc-1",
        vc_version="8.0.3.00900",
        services_running=["a", "b", "c"],
        services_stopped=["vmcam"],
        appliance_disks=[],
    )
    assessment = _assessment(vcenter)
    rows = {r.component: r for r in summary.component_status_rows(assessment)}
    row = rows["vCenter Server"]
    assert row.status == "Healthy"
    assert "version 8.0.3.00900" in row.remarks
    assert "3 service(s) running, 1 stopped" in row.remarks
