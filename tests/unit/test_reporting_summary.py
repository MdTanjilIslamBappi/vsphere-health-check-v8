from vhealth.models.assessment import Assessment, AssessmentMetadata
from vhealth.models.findings import Finding, Severity
from vhealth.models.host import Datastore, HostInfo, NetworkSwitch, VirtualMachine
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
    assert rows["Time Synchronization (NTP)"].status == summary.NOT_ASSESSED
    assert rows["Kernel Coredump Configuration"].status == summary.NOT_ASSESSED
    assert rows["VIB Acceptance Level"].status == summary.NOT_ASSESSED
    assert rows["Network (vSwitch/DVS)"].status == summary.NOT_ASSESSED
    assert rows["ConfigStore Integrity"].status == summary.NOT_ASSESSED
    assert rows["Migration Network Health"].status == summary.NOT_ASSESSED
    assert rows["Pending Reboot (Image Profile)"].status == summary.NOT_ASSESSED
    assert rows["Memory Health"].status == summary.NOT_ASSESSED


def test_component_status_rows_reports_real_datastore_and_vm_data_when_present():
    """Datastore names and running-VM identity come from the ESXi hosts

    themselves, not vCenter, so a bundle with no vCenter member at all
    must still show them as assessed rather than a blanket "Not assessed".
    """
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        datastores=[Datastore(name="DS01", uuid="uuid-1", naa_ids=["naa.1"])],
        virtual_machines=[VirtualMachine(name="vm-a", uuid="vm-uuid-1")],
        vm_inventory_available=True,
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Datastores"].status != summary.NOT_ASSESSED
    assert "DS01" in rows["Datastores"].remarks or "1 distinct" in rows["Datastores"].remarks
    assert rows["Virtual Machines"].status != summary.NOT_ASSESSED
    assert "1 running VM" in rows["Virtual Machines"].remarks
    # No VM reported EVC-mask evidence here, so EVC must stay not assessed --
    # it has no host-side source on its own.
    assert rows["EVC Mode"].status == summary.NOT_ASSESSED


def test_component_status_rows_reports_evc_mask_evidence_from_vm_logs():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        virtual_machines=[
            VirtualMachine(name="vm-a", uuid="u1", no_evc_masks_observed=True),
            VirtualMachine(name="vm-b", uuid="u2", no_evc_masks_observed=False),
        ],
        vm_inventory_available=True,
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["EVC Mode"].status != summary.NOT_ASSESSED
    assert "1 of 2" in rows["EVC Mode"].remarks
    assert "No EVC CPU-feature masking" in rows["EVC Mode"].remarks


def test_component_status_rows_reports_ntp_not_synchronized():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        ntp_data_available=True,
        ntp_time_synchronized=False,
        ntp_servers=["10.10.18.24"],
    )
    finding = Finding(
        rule_id="hardware.ntp_not_synchronized",
        title="Host clock is not synchronized via NTP",
        severity=Severity.MEDIUM,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    ntp_row = rows["Time Synchronization (NTP)"]
    assert ntp_row.status != summary.NOT_ASSESSED
    assert "h1" in ntp_row.remarks
    assert "Time Synchronized" in ntp_row.remarks


def test_component_status_rows_reports_ntp_healthy_when_all_synced():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        ntp_data_available=True,
        ntp_time_synchronized=True,
        ntp_servers=["10.10.18.24"],
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    ntp_row = rows["Time Synchronization (NTP)"]
    assert ntp_row.status == "Healthy"


def test_component_status_rows_reports_coredump_not_configured():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        coredump_data_available=True,
        coredump_configured=False,
    )
    finding = Finding(
        rule_id="hardware.coredump_not_configured",
        title="No active kernel-coredump target configured",
        severity=Severity.MEDIUM,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    coredump_row = rows["Kernel Coredump Configuration"]
    assert coredump_row.status != summary.NOT_ASSESSED
    assert "h1" in coredump_row.remarks


def test_component_status_rows_reports_coredump_healthy_when_configured():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        coredump_data_available=True,
        coredump_configured=True,
        coredump_active_path="/vmfs/volumes/uuid/vmkdump/x.dumpfile",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    coredump_row = rows["Kernel Coredump Configuration"]
    assert coredump_row.status == "Healthy"


def test_component_status_rows_reports_community_supported_vib():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        vib_data_available=True,
        community_supported_vibs=["my-community-driver"],
    )
    finding = Finding(
        rule_id="hardware.community_supported_vib_installed",
        title="Host has a CommunitySupported (unsupported) VIB installed",
        severity=Severity.MEDIUM,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    vib_row = rows["VIB Acceptance Level"]
    assert vib_row.status != summary.NOT_ASSESSED
    assert "h1" in vib_row.remarks


def test_component_status_rows_reports_vib_healthy_when_no_community_vibs():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        vib_data_available=True,
        community_supported_vibs=[],
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    vib_row = rows["VIB Acceptance Level"]
    assert vib_row.status == "Healthy"


def test_component_status_rows_reports_configstore_integrity_failure():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        configstore_data_available=True,
        configstore_integrity_ok=False,
    )
    finding = Finding(
        rule_id="hardware.configstore_integrity_check_failed",
        title="ConfigStore database integrity check did not report 'ok'",
        severity=Severity.CRITICAL,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    configstore_row = rows["ConfigStore Integrity"]
    assert configstore_row.status == "Attention Needed"
    assert "h1" in configstore_row.remarks
    assert (
        summary.category_for_rule_id("hardware.configstore_integrity_check_failed")
        == "Other"
    )


def test_component_status_rows_reports_configstore_healthy_when_ok():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        configstore_data_available=True,
        configstore_integrity_ok=True,
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["ConfigStore Integrity"].status == "Healthy"


def test_component_status_rows_reports_mobility_health_check_error():
    from vhealth.models.host import MobilityNetworkCheck

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        mobility_data_available=True,
        mobility_checks=[MobilityNetworkCheck(net_service="VMOTION", status="ERROR")],
    )
    finding = Finding(
        rule_id="network.mobility_health_check_error",
        title="VMOTION network health check reported ERROR",
        severity=Severity.HIGH,
        summary="...",
        affected_host="h1",
        affected_object="VMOTION",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    mobility_row = rows["Migration Network Health"]
    assert mobility_row.status == "Attention Needed"
    assert "VMOTION" in mobility_row.remarks
    assert summary.category_for_rule_id("network.mobility_health_check_error") == "Network"


def test_component_status_rows_reports_mobility_healthy_when_no_errors():
    from vhealth.models.host import MobilityNetworkCheck

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        mobility_data_available=True,
        mobility_checks=[MobilityNetworkCheck(net_service="VMOTION", status="OK")],
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Migration Network Health"].status == "Healthy"


def test_component_status_rows_reports_pending_reboot_image():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        pending_reboot_data_available=True,
        pending_reboot_image_name="(Updated) ESXi-8.0U3j-standard",
    )
    finding = Finding(
        rule_id="hardware.pending_reboot_image",
        title="Host has an image profile staged but not yet applied by a reboot",
        severity=Severity.MEDIUM,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    pending_row = rows["Pending Reboot (Image Profile)"]
    assert pending_row.status == "Advisory"
    assert "h1" in pending_row.remarks
    assert summary.category_for_rule_id("hardware.pending_reboot_image") == "Other"


def test_component_status_rows_reports_pending_reboot_healthy_when_none_staged():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        pending_reboot_data_available=True,
        pending_reboot_image_name=None,
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Pending Reboot (Image Profile)"].status == "Healthy"


def test_component_status_rows_reports_degraded_memory_hardware_health():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        memory_health_data_available=True,
        memory_hardware_state="Red",
        memory_reservation_state="Green",
    )
    finding = Finding(
        rule_id="hardware.memory_hardware_health_degraded",
        title="ESXi reports degraded physical memory (ECC) health",
        severity=Severity.CRITICAL,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    memory_row = rows["Memory Health"]
    assert memory_row.status == "Attention Needed"
    assert "h1" in memory_row.remarks
    assert summary.category_for_rule_id("hardware.memory_hardware_health_degraded") == "Memory"
    assert summary.category_for_rule_id("hardware.memory_reservation_health_degraded") == "Memory"


def test_component_status_rows_reports_memory_healthy_when_all_green():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        memory_health_data_available=True,
        memory_hardware_state="Green",
        memory_reservation_state="Green",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Memory Health"].status == "Healthy"


def test_component_status_rows_reports_vswitch_single_uplink():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        network_switch_data_available=True,
        network_switches=[NetworkSwitch(name="DVS-01", uplinks=["vmnic0"])],
    )
    finding = Finding(
        rule_id="network.vswitch_single_uplink",
        title="Network switch has only one uplink (no NIC redundancy)",
        severity=Severity.MEDIUM,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    network_row = rows["Network (vSwitch/DVS)"]
    assert network_row.status != summary.NOT_ASSESSED
    assert "1 switch(es) with only one uplink" in network_row.remarks


def test_component_status_rows_reports_network_healthy_when_redundant():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        network_switch_data_available=True,
        network_switches=[NetworkSwitch(name="DVS-01", uplinks=["vmnic0", "vmnic1"])],
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    network_row = rows["Network (vSwitch/DVS)"]
    assert network_row.status == "Healthy"


def test_component_status_rows_reports_vswitch_uplink_link_down():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        network_switch_data_available=True,
        network_switches=[NetworkSwitch(name="DVS-01", uplinks=["vmnic0", "vmnic1"])],
    )
    finding = Finding(
        rule_id="network.vswitch_uplink_link_down",
        title="Network switch uplink is configured but has no physical link",
        severity=Severity.HIGH,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    network_row = rows["Network (vSwitch/DVS)"]
    assert network_row.status != summary.NOT_ASSESSED
    assert "configured uplink that has no physical link" in network_row.remarks
    assert summary.category_for_rule_id("network.vswitch_uplink_link_down") == "Network"
    assert summary.category_for_rule_id("network.vswitch_all_uplinks_down") == "Network"


def test_virtual_machine_inventory_rows_resolve_datastore_name():
    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        datastores=[Datastore(name="DS01", uuid="uuid-1", naa_ids=[])],
        virtual_machines=[
            VirtualMachine(name="vm-b", uuid="vm-uuid-2", datastore_uuid="uuid-1"),
        ],
        vm_inventory_available=True,
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = summary.virtual_machine_inventory_rows(assessment)
    assert len(rows) == 1
    assert rows[0].name == "vm-b"
    assert rows[0].host == "h1"
    assert rows[0].datastore == "DS01"


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


def test_component_status_rows_counts_multipath_finding_as_storage_hardware():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(hostname="h1", bundle_source="h1")
    finding = Finding(
        rule_id="storage.multipath_all_paths_dead",
        title="All multipathing paths to a storage device are dead",
        severity=Severity.CRITICAL,
        summary="...",
        affected_host="h1",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Storage & Hardware Findings"].status == "Attention Needed"
    assert rows["Overall"].status == "Attention Needed"


def test_cluster_status_row_counts_host_with_only_resolved_cluster_name():
    """A host resolved to a cluster purely via vCenter-side membership data

    (no self-reported ``cluster_id``) must still show up as clustered, not
    be silently dropped into the standalone bucket.
    """
    host = HostInfo(hostname="h1", bundle_source="h1", cluster_name="EAMSC2")
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    cluster_row = rows["Cluster Status"]
    assert "EAMSC2" in cluster_row.remarks
    assert "1 host" in cluster_row.remarks
    assert "standalone" not in cluster_row.remarks


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


def test_recommendation_groups_assign_category_by_rule_id():
    findings = [
        Finding(
            rule_id="storage.pdl_detected", title="PDL", severity=Severity.CRITICAL,
            summary="...", affected_host="h1",
        ),
        Finding(
            rule_id="hardware.ipmi_sensor_asserted", title="Sensor", severity=Severity.HIGH,
            summary="...", affected_host="h1",
        ),
        Finding(
            rule_id="fleet.cpu_model_mismatch", title="CPU mismatch", severity=Severity.MEDIUM,
            summary="...",
        ),
        Finding(
            rule_id="coverage.limited_diagnostic_data", title="Limited data",
            severity=Severity.LOW, summary="...", affected_host="h2",
        ),
    ]
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=findings)
    by_title = {g.title: g.category for g in summary.recommendation_groups(assessment)}
    assert by_title["PDL"] == "Storage"
    assert by_title["Sensor"] == "Hardware / SEL"
    assert by_title["CPU mismatch"] == "CPU"
    assert by_title["Limited data"] == "Other"


def test_component_status_rows_fold_sel_findings_into_storage_hardware_row():
    findings = [
        Finding(
            rule_id="hardware.sel_ecc_uncorrectable", title="ECC", severity=Severity.CRITICAL,
            summary="...", affected_host="h1",
        ),
    ]
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=findings)
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    assert rows["Storage & Hardware Findings"].status == "Attention Needed"
    assert summary.category_for_rule_id("hardware.sel_ecc_uncorrectable") == "Hardware / SEL"


def test_component_status_rows_reports_datastore_usage_finding():
    from vhealth.models.findings import Finding, Severity

    host = HostInfo(
        hostname="h1",
        bundle_source="h1",
        datastores=[Datastore(name="DS-01", uuid="uuid-1", naa_ids=["naa.1"])],
    )
    finding = Finding(
        rule_id="fleet.datastore_usage_warning",
        title="Datastore is running low on free space",
        severity=Severity.MEDIUM,
        summary="...",
        affected_object="DS-01",
    )
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[finding])
    rows = {row.component: row for row in summary.component_status_rows(assessment)}
    datastores_row = rows["Datastores"]
    assert datastores_row.status == "Advisory"
    assert "1 nearing/at capacity" in datastores_row.remarks
    assert summary.category_for_rule_id("fleet.datastore_usage_warning") == "Storage"
    assert summary.category_for_rule_id("fleet.datastore_usage_critical") == "Storage"


def test_recommendation_groups_carry_host_tagged_evidence():
    findings = [
        Finding(
            rule_id="storage.pdl_detected", title="PDL", severity=Severity.CRITICAL,
            summary="...", affected_host="h1", evidence=["[pdl_error] some log line"],
        ),
    ]
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=findings)
    groups = summary.recommendation_groups(assessment)
    assert groups[0].evidence == ["h1: [pdl_error] some log line"]


def test_findings_by_category_groups_and_orders_for_the_findings_log():
    findings = [
        Finding(
            rule_id="coverage.limited_diagnostic_data", title="Limited data",
            severity=Severity.LOW, summary="...", affected_host="h2",
        ),
        Finding(
            rule_id="storage.pdl_detected", title="PDL", severity=Severity.CRITICAL,
            summary="...", affected_host="h1",
        ),
        Finding(
            rule_id="storage.device_not_on", title="Device not on", severity=Severity.HIGH,
            summary="...", affected_host="h1",
        ),
        Finding(
            rule_id="network.vswitch_single_uplink", title="Single uplink",
            severity=Severity.MEDIUM, summary="...", affected_host="h1",
        ),
    ]
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=findings)
    grouped = summary.findings_by_category(assessment)
    categories = [c for c, _ in grouped]
    # Storage before Network before Other, per CATEGORY_DISPLAY_ORDER -- not
    # insertion order, which would have put "Other" (limited data) first.
    assert categories == ["Storage", "Network", "Other"]
    storage_findings = next(fs for c, fs in grouped if c == "Storage")
    # Within a category, worst severity first.
    assert [f.title for f in storage_findings] == ["PDL", "Device not on"]


def test_findings_by_category_is_empty_when_no_findings_were_raised():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    assert summary.findings_by_category(assessment) == []


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


def test_detailed_observations_mentions_default_log_window():
    assessment = Assessment(metadata=_metadata(), hosts=[], findings=[])
    items = summary.detailed_observations(assessment)
    assert any("13 week(s) (91 days)" in item for item in items)


def test_detailed_observations_reflects_configured_log_window():
    host = HostInfo(hostname="h1", bundle_source="h1", log_window_weeks=4)
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    items = summary.detailed_observations(assessment)
    assert any("4 week(s) (28 days)" in item for item in items)


def test_executive_summary_text_reflects_configured_log_window():
    host = HostInfo(hostname="h1", bundle_source="h1", log_window_weeks=26)
    assessment = Assessment(metadata=_metadata(), hosts=[host], findings=[])
    text = summary.executive_summary_text(assessment)
    assert "26 week(s) (182 days)" in text
