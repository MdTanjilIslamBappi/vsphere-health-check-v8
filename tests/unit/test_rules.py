from synthetic_bundle import build_host_dir

from vhealth.models.host import HostInfo, MobilityNetworkCheck, NetworkSwitch
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


def test_ntp_not_synchronized_raises_finding(tmp_path):
    host = _assessed_host(tmp_path, ntp_time_synchronized=False)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.ntp_not_synchronized" in rule_ids


def test_ntp_synchronized_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, ntp_time_synchronized=True)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.ntp_not_synchronized" not in rule_ids


def test_coredump_not_configured_raises_finding(tmp_path):
    host = _assessed_host(tmp_path, coredump_configured=False)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.coredump_not_configured" in rule_ids


def test_coredump_configured_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, coredump_configured=True)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.coredump_not_configured" not in rule_ids


def test_community_supported_vib_raises_finding(tmp_path):
    host = _assessed_host(tmp_path, community_supported_vibs=["my-community-driver"])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.community_supported_vib_installed" in rule_ids


def test_no_community_supported_vib_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, community_supported_vibs=[])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.community_supported_vib_installed" not in rule_ids


def test_multipath_all_paths_dead_raises_critical_finding(tmp_path):
    host = _assessed_host(
        tmp_path, multipath_dead_paths=2, multipath_total_paths=2
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "storage.multipath_all_paths_dead" in rule_ids
    assert "storage.multipath_reduced_redundancy" not in rule_ids


def test_multipath_reduced_redundancy_raises_high_finding(tmp_path):
    host = _assessed_host(
        tmp_path, multipath_dead_paths=1, multipath_total_paths=2
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "storage.multipath_reduced_redundancy" in rule_ids
    assert "storage.multipath_all_paths_dead" not in rule_ids


def test_multipath_no_dead_paths_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path, multipath_dead_paths=0, multipath_total_paths=2
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "storage.multipath_all_paths_dead" not in rule_ids
    assert "storage.multipath_reduced_redundancy" not in rule_ids


def test_vswitch_single_uplink_raises_finding(tmp_path):
    host = _assessed_host(tmp_path, vswitch_uplinks=["vmnic0"])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_single_uplink" in rule_ids


def test_vswitch_redundant_uplinks_raise_no_finding(tmp_path):
    host = _assessed_host(tmp_path, vswitch_uplinks=["vmnic0", "vmnic1"])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_single_uplink" not in rule_ids


def test_vswitch_single_virtual_bmc_uplink_raises_no_finding(tmp_path):
    """The BMC/iDRAC out-of-band vSwitch's single vusb0 uplink is not a

    real NIC-redundancy risk and must not be flagged.
    """
    host = _assessed_host(tmp_path, vswitch_uplinks=["vusb0"])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_single_uplink" not in rule_ids


def test_vswitch_mtu_mismatch_raises_fleet_finding():
    host_a = HostInfo(
        hostname="host-a",
        bundle_source="a",
        network_switches=[NetworkSwitch(name="DVS-01", mtu=1500, uplinks=["vmnic0", "vmnic1"])],
    )
    host_b = HostInfo(
        hostname="host-b",
        bundle_source="b",
        network_switches=[NetworkSwitch(name="DVS-01", mtu=9000, uplinks=["vmnic0", "vmnic1"])],
    )
    findings = evaluate_all_fleet([host_a, host_b])
    rule_ids = {f.rule_id for f in findings}
    assert "fleet.vswitch_mtu_mismatch" in rule_ids


def test_vswitch_matching_mtu_raises_no_fleet_finding():
    host_a = HostInfo(
        hostname="host-a",
        bundle_source="a",
        network_switches=[NetworkSwitch(name="DVS-01", mtu=1500, uplinks=["vmnic0", "vmnic1"])],
    )
    host_b = HostInfo(
        hostname="host-b",
        bundle_source="b",
        network_switches=[NetworkSwitch(name="DVS-01", mtu=1500, uplinks=["vmnic0", "vmnic1"])],
    )
    findings = evaluate_all_fleet([host_a, host_b])
    rule_ids = {f.rule_id for f in findings}
    assert "fleet.vswitch_mtu_mismatch" not in rule_ids


def test_sel_ecc_uncorrectable_raises_critical_finding(tmp_path):
    host = _assessed_host(tmp_path, ipmi_sel_message="Assert + Memory Uncorrectable ECC")
    findings = evaluate_all([host])
    ecc_findings = [f for f in findings if f.rule_id == "hardware.sel_ecc_uncorrectable"]
    assert len(ecc_findings) == 1
    assert ecc_findings[0].severity.value == "critical"


def test_sel_drive_predictive_failure_raises_high_finding(tmp_path):
    host = _assessed_host(
        tmp_path, ipmi_sel_message="Assert + Drive Slot Predictive Failure"
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.sel_drive_predictive_failure" in rule_ids


def test_sel_deassert_message_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path, ipmi_sel_message="Deassert + Drive Slot Predictive Failure"
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert not any(rid.startswith("hardware.sel_") for rid in rule_ids)


def test_sel_event_older_than_one_quarter_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        ipmi_sel_message="Assert + Power Supply Failure status",
        ipmi_sel_when="2025-01-10T10:05:00",
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.sel_psu_failure" not in rule_ids


def test_vswitch_uplink_link_down_raises_high_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        vswitch_uplinks=["vmnic0", "vmnic1"],
        nic_link_status={"vmnic0": True, "vmnic1": False},
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_uplink_link_down" in rule_ids
    assert "network.vswitch_all_uplinks_down" not in rule_ids
    # Still has 2 configured uplinks, so the plain uplink-count rule must not fire.
    assert "network.vswitch_single_uplink" not in rule_ids


def test_vswitch_all_uplinks_down_raises_critical_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        vswitch_uplinks=["vmnic0", "vmnic1"],
        nic_link_status={"vmnic0": False, "vmnic1": False},
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_all_uplinks_down" in rule_ids
    assert "network.vswitch_uplink_link_down" not in rule_ids


def test_vswitch_uplinks_both_up_raise_no_link_down_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        vswitch_uplinks=["vmnic0", "vmnic1"],
        nic_link_status={"vmnic0": True, "vmnic1": True},
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_uplink_link_down" not in rule_ids
    assert "network.vswitch_all_uplinks_down" not in rule_ids


def test_vswitch_uplink_link_down_without_nic_data_raises_no_finding(tmp_path):
    """Without nicinfo.sh data, host.nic_link_up() returns None for every

    uplink, which must not be treated as "down" -- no NIC data should
    never silently masquerade as a finding.
    """
    host = _assessed_host(tmp_path, vswitch_uplinks=["vmnic0", "vmnic1"])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.vswitch_uplink_link_down" not in rule_ids
    assert "network.vswitch_all_uplinks_down" not in rule_ids


def test_datastore_usage_warning_raises_medium_finding(tmp_path):
    host = _assessed_host(
        tmp_path, datastore_name="DS-01", datastore_used_fraction=0.80
    )
    findings = evaluate_all_fleet([host])
    rule_ids = {f.rule_id for f in findings}
    assert "fleet.datastore_usage_warning" in rule_ids
    assert "fleet.datastore_usage_critical" not in rule_ids


def test_datastore_usage_critical_raises_high_finding(tmp_path):
    host = _assessed_host(
        tmp_path, datastore_name="DS-01", datastore_used_fraction=0.90
    )
    findings = evaluate_all_fleet([host])
    rule_ids = {f.rule_id for f in findings}
    assert "fleet.datastore_usage_critical" in rule_ids
    assert "fleet.datastore_usage_warning" not in rule_ids


def test_datastore_usage_healthy_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path, datastore_name="DS-01", datastore_used_fraction=0.50
    )
    findings = evaluate_all_fleet([host])
    rule_ids = {f.rule_id for f in findings}
    assert "fleet.datastore_usage_warning" not in rule_ids
    assert "fleet.datastore_usage_critical" not in rule_ids


def test_datastore_usage_dedups_shared_datastore_across_hosts(tmp_path):
    """The same shared VMFS volume is typically mounted -- and independently

    reported -- by every host in the assessment; it must raise one
    finding for the real problem, not one per host that happens to mount it.
    """
    host_a = _assessed_host(
        tmp_path / "a", datastore_name="DS-01", datastore_used_fraction=0.80
    )
    host_b = _assessed_host(
        tmp_path / "b", datastore_name="DS-01", datastore_used_fraction=0.80
    )
    findings = evaluate_all_fleet([host_a, host_b])
    usage_findings = [f for f in findings if f.rule_id == "fleet.datastore_usage_warning"]
    assert len(usage_findings) == 1


def test_configstore_integrity_check_failed_raises_critical_finding(tmp_path):
    host = _assessed_host(tmp_path, configstore_integrity_ok=False)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.configstore_integrity_check_failed" in rule_ids


def test_configstore_integrity_check_ok_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, configstore_integrity_ok=True)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.configstore_integrity_check_failed" not in rule_ids


def test_mobility_health_check_error_raises_high_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        mobility_status="ERROR",
        mobility_expected_destinations=22,
        mobility_tested_destinations=1,
    )
    findings = evaluate_all([host])
    mob = [f for f in findings if f.rule_id == "network.mobility_health_check_error"]
    assert len(mob) == 1
    assert mob[0].severity.value == "high"
    assert "1 of 22" in mob[0].evidence[1]


def test_mobility_health_check_ok_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path, mobility_status="OK", mobility_expected_destinations=5,
        mobility_tested_destinations=5,
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "network.mobility_health_check_error" not in rule_ids


def test_mobility_health_check_surfaces_specific_sub_check_error():
    """The PROVISIONING netService's distinctive "No valid vmknics" error

    (a host with no VMkernel adapter tagged for provisioning traffic) must
    be surfaced verbatim in the finding's evidence.
    """
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        mobility_data_available=True,
        mobility_checks=[
            MobilityNetworkCheck(
                net_service="PROVISIONING", status="ERROR", errors=["No valid vmknics"]
            )
        ],
    )
    findings = evaluate_all([host])
    mob = next(f for f in findings if f.rule_id == "network.mobility_health_check_error")
    assert "error: No valid vmknics" in mob.evidence


def test_pending_reboot_image_raises_medium_finding(tmp_path):
    host = _assessed_host(
        tmp_path, pending_reboot=True, pending_reboot_image_name="(Updated) ESXi-8.0U3j-standard"
    )
    findings = evaluate_all([host])
    pending = [f for f in findings if f.rule_id == "hardware.pending_reboot_image"]
    assert len(pending) == 1
    assert pending[0].severity.value == "medium"
    assert "(Updated) ESXi-8.0U3j-standard" in pending[0].summary


def test_pending_reboot_no_pending_image_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, pending_reboot=False)
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.pending_reboot_image" not in rule_ids


def test_memory_hardware_health_degraded_raises_critical_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        memory_hardware_state="Red",
        memory_reservation_state="Green",
        memory_uncorrected_errors_since_boot=1,
    )
    findings = evaluate_all([host])
    degraded = [f for f in findings if f.rule_id == "hardware.memory_hardware_health_degraded"]
    assert len(degraded) == 1
    assert degraded[0].severity.value == "critical"
    assert "Red" in degraded[0].summary
    assert "hardware.memory_reservation_health_degraded" not in {f.rule_id for f in findings}


def test_memory_reservation_health_degraded_raises_medium_finding(tmp_path):
    host = _assessed_host(
        tmp_path, memory_hardware_state="Green", memory_reservation_state="Yellow"
    )
    findings = evaluate_all([host])
    degraded = [
        f for f in findings if f.rule_id == "hardware.memory_reservation_health_degraded"
    ]
    assert len(degraded) == 1
    assert degraded[0].severity.value == "medium"
    assert "Yellow" in degraded[0].summary
    assert "hardware.memory_hardware_health_degraded" not in {f.rule_id for f in findings}


def test_memory_health_green_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path, memory_hardware_state="Green", memory_reservation_state="Green"
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "hardware.memory_hardware_health_degraded" not in rule_ids
    assert "hardware.memory_reservation_health_degraded" not in rule_ids


def test_nfs_datastore_inaccessible_raises_high_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        nfs_datastores=[
            {
                "volume_name": "NFS-V9",
                "remote_share_name": "/NFS-V9",
                "remote_host(s)": ["192.168.187.110"],
                "is_accessible": False,
                "is_mounted": False,
            }
        ],
    )
    findings = evaluate_all([host])
    nfs = [f for f in findings if f.rule_id == "storage.nfs_datastore_inaccessible"]
    assert len(nfs) == 1
    assert nfs[0].severity.value == "high"
    assert "NFS-V9" in nfs[0].summary
    assert nfs[0].affected_object == "NFS-V9"


def test_nfs_datastore_accessible_raises_no_finding(tmp_path):
    host = _assessed_host(
        tmp_path,
        nfs_datastores=[
            {
                "volume_name": "NFS-V9",
                "is_accessible": True,
                "is_mounted": True,
            }
        ],
    )
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "storage.nfs_datastore_inaccessible" not in rule_ids


def test_no_nfs_datastores_raises_no_finding(tmp_path):
    host = _assessed_host(tmp_path, nfs_datastores=[])
    findings = evaluate_all([host])
    rule_ids = {f.rule_id for f in findings}
    assert "storage.nfs_datastore_inaccessible" not in rule_ids


def test_log_window_weeks_controls_whether_sel_finding_fires(tmp_path):
    """An event 10 days before capture (within a 2-week window, outside a

    1-week one) must only raise a finding when the configured window is
    wide enough -- proving the window, not a hardcoded day count, drives
    the cutoff.
    """
    host_dir = build_host_dir(
        tmp_path,
        ipmi_sel_message="Assert + Memory Uncorrectable ECC",
        ipmi_sel_when="2026-01-05T10:05:00",  # the fixture's captured_on is 2026-01-15
    )

    def _assessed_with_window(weeks: int) -> HostInfo:
        host = HostInfo(hostname="h", bundle_source=str(host_dir), log_window_weeks=weeks)
        for module in PARSER_MODULES:
            host.parse_warnings.extend(module.parse(host_dir, host))
        return host

    narrow_findings = evaluate_all([_assessed_with_window(1)])
    wide_findings = evaluate_all([_assessed_with_window(2)])
    assert "hardware.sel_ecc_uncorrectable" not in {f.rule_id for f in narrow_findings}
    assert "hardware.sel_ecc_uncorrectable" in {f.rule_id for f in wide_findings}


def test_fleet_disabled_rules_are_excluded():
    host_a = HostInfo(hostname="host-a", bundle_source="a", cpu_model="Intel Xeon Gold 6258R")
    host_b = HostInfo(hostname="host-b", bundle_source="b", cpu_model="Intel Xeon Gold 6430")
    findings = evaluate_all_fleet(
        [host_a, host_b], disabled_rules=("fleet.cpu_model_mismatch",)
    )
    assert findings == []
