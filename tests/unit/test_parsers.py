from pathlib import Path

from synthetic_bundle import build_host_dir

from vhealth.models.host import HostInfo
from vhealth.parsers import (
    configstore,
    coredump,
    datastore,
    hardware_inventory,
    ipmi_sel,
    multipath,
    nic_link,
    ntp,
    readme,
    sensors,
    smart,
    storage_core,
    system_version,
    vib,
    vm_inventory,
    vmk_log,
    vswitch,
)


def _build_host(tmp_path, **kwargs) -> tuple[Path, HostInfo]:
    host_dir = build_host_dir(tmp_path, **kwargs)
    host = HostInfo(hostname="placeholder", bundle_source=str(host_dir))
    return host_dir, host


def test_readme_parser_extracts_capture_metadata(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = readme.parse(host_dir, host)
    assert warnings == []
    assert host.captured_on == "2026-01-15 10:00:00.000000"
    assert host.vm_support_version == "v4.1"


def test_system_version_parser_extracts_version_and_hostname(tmp_path):
    host_dir, host = _build_host(tmp_path, hostname="my-host.example.test")
    warnings = system_version.parse(host_dir, host)
    assert warnings == []
    assert host.esxi_version == "8.0.3 Update 3"
    assert host.esxi_build == "Releasebuild-99999999"
    assert host.hostname == "my-host.example.test"


def test_storage_core_parser_extracts_adapters_and_devices(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = storage_core.parse(host_dir, host)
    assert warnings == []
    assert len(host.storage_adapters) == 1
    assert host.storage_adapters[0].device == "vmhba2"
    assert len(host.storage_devices) == 2
    local = [d for d in host.storage_devices if d.is_local]
    assert local and local[0].device == "t10.synthetic_local_nvme"


def test_datastore_parser_extracts_name_and_backing_device(tmp_path):
    host_dir, host = _build_host(tmp_path, datastore_name="Synthetic-Datastore-01")
    warnings = datastore.parse(host_dir, host)
    assert warnings == []
    assert len(host.datastores) == 1
    assert host.datastores[0].name == "Synthetic-Datastore-01"
    assert host.datastores[0].naa_ids == ["naa.6000000000000000000000000000001"]
    assert (
        host.datastore_for_naa("naa.6000000000000000000000000000001")
        == "Synthetic-Datastore-01"
    )
    assert host.datastore_for_naa("naa.doesnotexist") is None


def test_datastore_parser_reports_warning_when_no_dump_present(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = datastore.parse(host_dir, host)
    assert warnings != []
    assert host.datastores == []


def test_datastore_parser_extracts_capacity_and_available_bytes(tmp_path):
    host_dir, host = _build_host(
        tmp_path, datastore_name="Synthetic-Datastore-01", datastore_used_fraction=0.9
    )
    warnings = datastore.parse(host_dir, host)
    assert warnings == []
    ds = host.datastores[0]
    assert ds.capacity_bytes == 1000 * 1024**3
    assert ds.available_bytes == int(1000 * 1024**3 * (1 - 0.9))


def test_datastore_parser_leaves_capacity_none_when_not_given(tmp_path):
    host_dir, host = _build_host(tmp_path, datastore_name="Synthetic-Datastore-01")
    datastore.parse(host_dir, host)
    ds = host.datastores[0]
    assert ds.capacity_bytes is None
    assert ds.available_bytes is None


def test_vm_inventory_parser_extracts_running_vms_and_resolves_datastore(tmp_path):
    host_dir, host = _build_host(
        tmp_path, datastore_name="Synthetic-Datastore-01", vm_names=["vm-alpha", "vm-beta"]
    )
    datastore.parse(host_dir, host)
    warnings = vm_inventory.parse(host_dir, host)
    assert warnings == []
    assert host.vm_inventory_available is True
    names = sorted(vm.name for vm in host.virtual_machines)
    assert names == ["vm-alpha", "vm-beta"]
    vm = next(v for v in host.virtual_machines if v.name == "vm-alpha")
    assert vm.uuid is not None
    assert host.datastore_name_for_uuid(vm.datastore_uuid) == "Synthetic-Datastore-01"


def test_vm_inventory_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = vm_inventory.parse(host_dir, host)
    assert warnings != []
    assert host.vm_inventory_available is False
    assert host.virtual_machines == []


def test_vm_inventory_parser_observes_no_evc_masks_from_vm_power_on_log(tmp_path):
    host_dir, host = _build_host(
        tmp_path, vm_names=["vm-gamma"], vm_no_evc_masks=True
    )
    vm_inventory.parse(host_dir, host)
    vm = host.virtual_machines[0]
    assert vm.no_evc_masks_observed is True


def test_vm_inventory_parser_leaves_evc_unobserved_without_vm_log(tmp_path):
    host_dir, host = _build_host(tmp_path, vm_names=["vm-delta"])
    vm_inventory.parse(host_dir, host)
    vm = host.virtual_machines[0]
    assert vm.no_evc_masks_observed is False


def test_vmk_log_evidence_is_annotated_with_datastore_name(tmp_path):
    from vhealth.rules.log_rules import RULES

    host_dir, host = _build_host(
        tmp_path, include_pdl_warning=True, datastore_name="Synthetic-Datastore-01"
    )
    readme.parse(host_dir, host)
    datastore.parse(host_dir, host)
    vmk_log.parse(host_dir, host)
    findings = RULES[0].evaluate(host)
    pdl = next(f for f in findings if f.rule_id == "storage.pdl_detected")
    assert any("(datastore: Synthetic-Datastore-01)" in e for e in pdl.evidence)


def test_smart_parser_attaches_health_to_matching_device(tmp_path):
    host_dir, host = _build_host(tmp_path, smart_health="FAILED")
    storage_core.parse(host_dir, host)
    warnings = smart.parse(host_dir, host)
    assert warnings == []
    nvme = next(d for d in host.storage_devices if d.device == "t10.synthetic_local_nvme")
    assert nvme.smart_overall_health == "FAILED"
    assert nvme.smart_raw["Reallocated Sector Count"] == "0"


def test_sensors_parser_classifies_asserted_state(tmp_path):
    host_dir, host = _build_host(tmp_path, sensor_asserted=True)
    warnings = sensors.parse(host_dir, host)
    assert warnings == []
    ps1 = next(s for s in host.sensors if "PS1" in s.name)
    assert ps1.status == "asserted"


def test_sensors_parser_classifies_deasserted_state(tmp_path):
    host_dir, host = _build_host(tmp_path, sensor_asserted=False)
    sensors.parse(host_dir, host)
    ps1 = next(s for s in host.sensors if "PS1" in s.name)
    assert ps1.status == "deasserted"


def test_vmk_log_parser_counts_pdl_signal(tmp_path):
    host_dir, host = _build_host(tmp_path, include_pdl_warning=True)
    readme.parse(host_dir, host)  # sets host.captured_on, which the quarterly cutoff needs
    warnings = vmk_log.parse(host_dir, host)
    assert warnings == []
    assert host.log_signal_counts.get("pdl_error", 0) == 1
    assert any("pdl_error" in e for e in host.log_events)


def test_vmk_log_parser_no_pdl_signal_when_absent(tmp_path):
    host_dir, host = _build_host(tmp_path, include_pdl_warning=False)
    vmk_log.parse(host_dir, host)
    assert host.log_signal_counts.get("pdl_error", 0) == 0


def test_vmk_log_parser_excludes_events_older_than_one_quarter(tmp_path):
    host_dir, host = _build_host(tmp_path, include_old_pdl_warning=True)
    from vhealth.parsers import readme

    readme.parse(host_dir, host)  # sets host.captured_on, which the cutoff is computed from
    warnings = vmk_log.parse(host_dir, host)
    assert warnings == []
    assert host.log_signal_counts.get("pdl_error", 0) == 0
    assert host.log_signal_counts_excluded.get("pdl_error", 0) == 1


def test_vmk_log_parser_includes_recent_and_excludes_old_together(tmp_path):
    host_dir, host = _build_host(
        tmp_path, include_pdl_warning=True, include_old_pdl_warning=True
    )
    from vhealth.parsers import readme

    readme.parse(host_dir, host)
    vmk_log.parse(host_dir, host)
    assert host.log_signal_counts.get("pdl_error", 0) == 1
    assert host.log_signal_counts_excluded.get("pdl_error", 0) == 1


def test_parsers_report_warnings_when_evidence_missing(tmp_path):
    empty_dir = tmp_path / "empty-host"
    empty_dir.mkdir()
    host = HostInfo(hostname="x", bundle_source=str(empty_dir))
    assert readme.parse(empty_dir, host) != []
    assert system_version.parse(empty_dir, host) != []
    assert storage_core.parse(empty_dir, host) != []
    assert smart.parse(empty_dir, host) != []
    assert sensors.parse(empty_dir, host) != []
    assert vmk_log.parse(empty_dir, host) != []
    assert hardware_inventory.parse(empty_dir, host) != []
    assert vm_inventory.parse(empty_dir, host) != []
    assert ntp.parse(empty_dir, host) != []
    assert coredump.parse(empty_dir, host) != []
    assert vib.parse(empty_dir, host) != []
    assert multipath.parse(empty_dir, host) != []
    assert vswitch.parse(empty_dir, host) != []


def test_hardware_inventory_parser_extracts_server_and_cpu_model(tmp_path):
    host_dir, host = _build_host(
        tmp_path, server_model="PowerEdge R740xd", cpu_model="Intel(R) Xeon(R) Gold 6258R @ 2.70GHz"
    )
    warnings = hardware_inventory.parse(host_dir, host)
    assert warnings == []
    assert host.server_manufacturer == "Synthetic Inc."
    assert host.server_model == "PowerEdge R740xd"
    assert host.cpu_model == "Intel(R) Xeon(R) Gold 6258R @ 2.70GHz"
    assert host.cpu_sockets == 2


def test_hardware_inventory_parser_extracts_management_ip(tmp_path):
    host_dir, host = _build_host(tmp_path, management_ip="10.1.2.3")
    hardware_inventory.parse(host_dir, host)
    assert host.management_ip == "10.1.2.3"


def test_hardware_inventory_parser_extracts_cluster_membership(tmp_path):
    host_dir, host = _build_host(tmp_path, cluster_id="domain-c1001")
    hardware_inventory.parse(host_dir, host)
    assert host.cluster_id == "domain-c1001"
    assert host.cluster_in_alarm is False


def test_ntp_parser_extracts_sync_status_and_servers(tmp_path):
    host_dir, host = _build_host(tmp_path, ntp_time_synchronized=False)
    warnings = ntp.parse(host_dir, host)
    assert warnings == []
    assert host.ntp_data_available is True
    assert host.ntp_enabled is True
    assert host.ntp_time_synchronized is False
    assert host.ntp_servers == ["10.10.18.24"]


def test_ntp_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = ntp.parse(host_dir, host)
    assert warnings != []
    assert host.ntp_data_available is False


def test_coredump_parser_extracts_configured_state(tmp_path):
    host_dir, host = _build_host(tmp_path, coredump_configured=True)
    warnings = coredump.parse(host_dir, host)
    assert warnings == []
    assert host.coredump_data_available is True
    assert host.coredump_configured is True
    assert host.coredump_active_path == (
        "/vmfs/volumes/synthetic-uuid/vmkdump/synthetic.dumpfile"
    )


def test_coredump_parser_extracts_not_configured_state(tmp_path):
    host_dir, host = _build_host(tmp_path, coredump_configured=False)
    warnings = coredump.parse(host_dir, host)
    assert warnings == []
    assert host.coredump_data_available is True
    assert host.coredump_configured is False
    assert host.coredump_active_path is None


def test_coredump_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = coredump.parse(host_dir, host)
    assert warnings != []
    assert host.coredump_data_available is False


def test_vib_parser_extracts_community_supported_vibs(tmp_path):
    host_dir, host = _build_host(
        tmp_path, community_supported_vibs=["my-community-driver"]
    )
    warnings = vib.parse(host_dir, host)
    assert warnings == []
    assert host.vib_data_available is True
    assert host.community_supported_vibs == ["my-community-driver"]


def test_vib_parser_reports_no_community_vibs_when_none_installed(tmp_path):
    host_dir, host = _build_host(tmp_path, community_supported_vibs=[])
    warnings = vib.parse(host_dir, host)
    assert warnings == []
    assert host.vib_data_available is True
    assert host.community_supported_vibs == []


def test_vib_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = vib.parse(host_dir, host)
    assert warnings != []
    assert host.vib_data_available is False


def test_multipath_parser_aggregates_dead_paths_per_device(tmp_path):
    host_dir, host = _build_host(
        tmp_path, multipath_dead_paths=1, multipath_total_paths=2
    )
    warnings = multipath.parse(host_dir, host)
    assert warnings == []
    assert host.multipath_data_available is True
    assert len(host.multipath_devices) == 1
    device = host.multipath_devices[0]
    assert device.total_paths == 2
    assert device.dead_paths == 1
    assert device.device == "naa.6000000000000000000000000000099"


def test_multipath_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = multipath.parse(host_dir, host)
    assert warnings != []
    assert host.multipath_data_available is False


def test_vswitch_parser_extracts_dvs_name_mtu_and_uplinks(tmp_path):
    host_dir, host = _build_host(
        tmp_path, vswitch_name="DVS-01", vswitch_uplinks=["vmnic0", "vmnic1"], vswitch_mtu=9000
    )
    warnings = vswitch.parse(host_dir, host)
    assert warnings == []
    assert host.network_switch_data_available is True
    assert len(host.network_switches) == 1
    switch = host.network_switches[0]
    assert switch.name == "DVS-01"
    assert switch.is_distributed is True
    assert switch.mtu == 9000
    assert switch.uplinks == ["vmnic0", "vmnic1"]


def test_vswitch_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = vswitch.parse(host_dir, host)
    assert warnings != []
    assert host.network_switch_data_available is False


def test_ipmi_sel_parser_counts_drive_predictive_failure_signal(tmp_path):
    host_dir, host = _build_host(
        tmp_path, ipmi_sel_message="Assert + Drive Slot Predictive Failure"
    )
    readme.parse(host_dir, host)  # sets host.captured_on, which the quarterly cutoff needs
    warnings = ipmi_sel.parse(host_dir, host)
    assert warnings == []
    assert host.log_signal_counts.get("sel_drive_predictive_failure", 0) == 1
    assert any("sel_drive_predictive_failure" in e for e in host.log_events)


def test_ipmi_sel_parser_ignores_deassert_and_unmapped_messages(tmp_path):
    host_dir, host = _build_host(
        tmp_path, ipmi_sel_message="Deassert + Drive Slot Predictive Failure"
    )
    readme.parse(host_dir, host)
    warnings = ipmi_sel.parse(host_dir, host)
    assert warnings == []
    assert host.log_signal_counts == {}


def test_ipmi_sel_parser_excludes_events_older_than_one_quarter(tmp_path):
    host_dir, host = _build_host(
        tmp_path,
        ipmi_sel_message="Assert + Memory Uncorrectable ECC",
        ipmi_sel_when="2025-01-10T10:05:00",
    )
    readme.parse(host_dir, host)  # captured_on is 2026-01-15; this is ~1 year earlier
    warnings = ipmi_sel.parse(host_dir, host)
    assert warnings == []
    assert host.log_signal_counts.get("sel_ecc_uncorrectable", 0) == 0
    assert host.log_signal_counts_excluded.get("sel_ecc_uncorrectable", 0) == 1


def test_ipmi_sel_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = ipmi_sel.parse(host_dir, host)
    assert warnings != []


def test_nic_link_parser_extracts_link_state_and_stops_at_blank_line(tmp_path):
    host_dir, host = _build_host(
        tmp_path, nic_link_status={"vmnic0": True, "vmnic1": False}
    )
    warnings = nic_link.parse(host_dir, host)
    assert warnings == []
    assert host.nic_data_available is True
    assert len(host.nic_adapters) == 2
    assert host.nic_link_up("vmnic0") is True
    assert host.nic_link_up("vmnic1") is False
    assert host.nic_link_up("vmnic99") is None


def test_nic_link_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = nic_link.parse(host_dir, host)
    assert warnings != []
    assert host.nic_data_available is False


def test_configstore_parser_reports_ok(tmp_path):
    host_dir, host = _build_host(tmp_path, configstore_integrity_ok=True)
    warnings = configstore.parse(host_dir, host)
    assert warnings == []
    assert host.configstore_data_available is True
    assert host.configstore_integrity_ok is True


def test_configstore_parser_reports_failed_integrity_check(tmp_path):
    host_dir, host = _build_host(tmp_path, configstore_integrity_ok=False)
    warnings = configstore.parse(host_dir, host)
    assert warnings == []
    assert host.configstore_data_available is True
    assert host.configstore_integrity_ok is False


def test_configstore_parser_reports_warning_when_file_missing(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = configstore.parse(host_dir, host)
    assert warnings != []
    assert host.configstore_data_available is False
