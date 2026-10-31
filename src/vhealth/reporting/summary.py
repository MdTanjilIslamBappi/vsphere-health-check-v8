"""Pure data-shaping helpers shared by the DOCX and HTML report renderers.

Keeps the aggregation/judgement logic -- what counts as "Healthy" vs
"Attention Needed", which findings belong to which component bucket --
in one place, tested once, instead of duplicated between two template
engines. Nothing here reaches outside the already-computed ``Assessment``;
it only reshapes it for display.

The main report mirrors a customer-facing executive health-check report
convention (cover page, version history, a Component/Status/Remarks
table, an ESXi host inventory table, a short bullet-list Scope section,
grouped recommendations); the full per-finding breakdown is deliberately
*not* part of this module's output for the main report -- see
``findings_log.py`` for the companion detailed-findings document.
"""

from __future__ import annotations

from dataclasses import dataclass

from vhealth.models.assessment import Assessment
from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo

_DEVICE_HEALTH_RULE_IDS = {
    "storage.smart_health_not_ok",
    "storage.smart_reallocated_sectors",
    "storage.device_not_on",
}
_LOG_SIGNAL_RULE_IDS = {
    "storage.pdl_detected",
    "storage.apd_detected",
    "storage.path_dead_detected",
    "storage.alua_path_connectivity",
    "storage.vob_problem_event",
}
_SENSOR_RULE_IDS = {
    "hardware.ipmi_sensor_asserted",
    "hardware.sel_ecc_uncorrectable",
    "hardware.sel_drive_predictive_failure",
    "hardware.sel_psu_failure",
    "hardware.sel_temperature_critical",
}
_PROCESSOR_RULE_IDS = {"fleet.cpu_model_mismatch"}
_NTP_RULE_IDS = {"hardware.ntp_not_synchronized"}
_COREDUMP_RULE_IDS = {"hardware.coredump_not_configured"}
_VIB_RULE_IDS = {"hardware.community_supported_vib_installed"}
_CONFIGSTORE_RULE_IDS = {"hardware.configstore_integrity_check_failed"}
_MOBILITY_RULE_IDS = {"network.mobility_health_check_error"}
_PENDING_REBOOT_RULE_IDS = {"hardware.pending_reboot_image"}
_MEMORY_RULE_IDS = {
    "hardware.memory_hardware_health_degraded",
    "hardware.memory_reservation_health_degraded",
}
_MULTIPATH_RULE_IDS = {
    "storage.multipath_all_paths_dead",
    "storage.multipath_reduced_redundancy",
}
_NETWORK_RULE_IDS = {
    "network.vswitch_single_uplink",
    "network.vswitch_uplink_link_down",
    "network.vswitch_all_uplinks_down",
    "fleet.vswitch_mtu_mismatch",
}
_STORAGE_HARDWARE_RULE_IDS = (
    _DEVICE_HEALTH_RULE_IDS | _LOG_SIGNAL_RULE_IDS | _SENSOR_RULE_IDS | _MULTIPATH_RULE_IDS
)
_DATASTORE_USAGE_RULE_IDS = {"fleet.datastore_usage_warning", "fleet.datastore_usage_critical"}

NOT_ASSESSED = "Not assessed"
_VCENTER_BUNDLE_REQUIRED = (
    "not assessed from this bundle; requires vCenter inventory/database access that the "
    "supplied capture does not provide"
)
_VCENTER_DB_NOT_PARSED = (
    "not assessed; the vCenter capture contains operational logs and appliance status but "
    "not a readable form of the vCenter inventory database"
)
# EVC baseline name and vCenter-level alarms exist only as rows in vCenter's own
# inventory database (vpxd's PostgreSQL store) -- no diagnostic bundle, from either
# an ESXi host or the vCenter appliance itself, ever contains a readable export of
# that database. This is unlike VM identity, datastore *names*, or datastore
# *capacity/free-space*, which each ESXi host reports about itself independently of
# vCenter (see below) -- only vCenter-side storage-policy compliance status is not.
_VCENTER_DB_FIELDS_UNAVAILABLE = (
    "is not assessed -- that exists only in vCenter's own inventory database, which no "
    "support bundle (host or vCenter) contains a readable export of"
)

_VCENTER_RULE_PREFIX = "vcenter."


# Host-only scope wording, shared between ``SCOPE_ITEMS`` (kept for
# backward compatibility with any static behaviour) and ``scope_items``.
_HOST_ONLY_SCOPE_ITEMS = (
    "ESXi host status and diagnostic data availability",
    "Storage device, adapter, SMART, and multipath path-state health",
    "Hardware sensor status (IPMI)",
    "Storage-related log signals (PDL/APD/ALUA/VOB), scoped to a configurable "
    "lookback window (1-26 weeks, default 13)",
    "Server and CPU hardware inventory, including processor compatibility across hosts",
    "Cluster/compute-resource membership, where host-reported in the bundle",
    f"Cluster EVC mode configuration -- not assessed; {_VCENTER_BUNDLE_REQUIRED}",
    "Datastore capacity and free-space usage, from each host's own VMFS volume "
    "data (a point-in-time snapshot at capture, not vCenter's historical trending)",
    f"Virtual machine inventory and resource utilization -- not assessed; "
    f"{_VCENTER_BUNDLE_REQUIRED}",
    f"vCenter-level active alarms -- not assessed; {_VCENTER_BUNDLE_REQUIRED}",
)

# Retained identifier for callers that build a host-only scope list
# without an Assessment at hand; prefer scope_items(assessment) instead.
SCOPE_ITEMS = _HOST_ONLY_SCOPE_ITEMS


def scope_items(assessment: Assessment) -> tuple[str, ...]:
    """Dynamic Scope section items, adjusted for what the bundle contained.

    Datastore *names and capacity/free-space* and running-VM identity come
    from each ESXi host's own files and need no vCenter bundle at all; EVC
    baseline, full VM inventory, and vCenter-level alarms exist only in
    vCenter's inventory database, which no bundle type exports.
    """
    vcenter = assessment.vcenter
    has_datastore_names = any(h.datastores for h in assessment.hosts)
    has_vm_inventory = any(h.vm_inventory_available for h in assessment.hosts)
    has_no_evc_mask_evidence = any(
        vm.no_evc_masks_observed for h in assessment.hosts for vm in h.virtual_machines
    )
    if has_no_evc_mask_evidence:
        evc_item = (
            "EVC CPU-feature masking status, observed from running VMs' own power-on "
            f"logs (not a read of the cluster's configured baseline, which "
            f"{_VCENTER_DB_FIELDS_UNAVAILABLE})"
        )
    else:
        evc_item = (
            "Cluster EVC mode configuration -- "
            f"{_VCENTER_BUNDLE_REQUIRED if vcenter is None else _VCENTER_DB_NOT_PARSED}"
        )
    if has_datastore_names:
        datastore_item = (
            "Datastore names and point-in-time capacity/free-space usage, identified "
            "from per-host VMFS volume dumps (see Recommendation for any nearing "
            f"capacity). vCenter-side storage-policy compliance status "
            f"{_VCENTER_DB_FIELDS_UNAVAILABLE}"
        )
    else:
        datastore_item = (
            "Datastore names and capacity/free-space usage -- not assessed; no VMFS "
            f"volume data found. vCenter-side storage-policy compliance status "
            f"{_VCENTER_DB_FIELDS_UNAVAILABLE}"
        )
    vm_item = (
        "Running VM identity, from each host's own record of what it is currently "
        "executing"
        if has_vm_inventory
        else "Running VM identity -- not assessed; no localcli vm process list data found"
    )
    if has_vm_inventory:
        vm_item += f". Powered-off VMs and resource utilization {_VCENTER_DB_FIELDS_UNAVAILABLE}"
    has_ntp_data = any(h.ntp_data_available for h in assessment.hosts)
    ntp_item = (
        "Host clock/NTP time-synchronization status (esxcli system ntp get)"
        if has_ntp_data
        else "Host clock/NTP time-synchronization status -- not assessed; no NTP data "
        "found in this bundle"
    )
    has_coredump_data = any(h.coredump_data_available for h in assessment.hosts)
    coredump_item = (
        "Kernel-coredump target configuration (esxcli system coredump file list)"
        if has_coredump_data
        else "Kernel-coredump target configuration -- not assessed; no coredump data "
        "found in this bundle"
    )
    has_vib_data = any(h.vib_data_available for h in assessment.hosts)
    vib_item = (
        "Installed VIB acceptance levels (esxcli software vib list)"
        if has_vib_data
        else "Installed VIB acceptance levels -- not assessed; no VIB data found in "
        "this bundle"
    )
    has_switch_data = any(h.network_switch_data_available for h in assessment.hosts)
    network_item = (
        "vSwitch/DVS uplink redundancy, physical uplink link state, and cross-host "
        "MTU consistency (esxcfg-vswitch -l, nicinfo.sh)"
        if has_switch_data
        else "vSwitch/DVS uplink redundancy and MTU consistency -- not assessed; no "
        "esxcfg-vswitch -l data found in this bundle"
    )
    has_configstore_data = any(h.configstore_data_available for h in assessment.hosts)
    configstore_item = (
        "ConfigStore (host-configuration database) integrity (sqlite3 PRAGMA "
        "integrity_check)"
        if has_configstore_data
        else "ConfigStore database integrity -- not assessed; no sqlite3 "
        "PRAGMA integrity_check data found in this bundle"
    )
    has_mobility_data = any(h.mobility_data_available for h in assessment.hosts)
    mobility_item = (
        "Migration-network (vMotion/Provisioning) health, per ESXi's own built-in "
        "check (mobility_network_health_check)"
        if has_mobility_data
        else "Migration-network (vMotion/Provisioning) health -- not assessed; no "
        "mobility_network_health_check data found in this bundle"
    )
    has_pending_reboot_data = any(h.pending_reboot_data_available for h in assessment.hosts)
    pending_reboot_item = (
        "Pending-reboot (staged-but-not-applied) image profile (esxcli software "
        "profile get --rebooting-image)"
        if has_pending_reboot_data
        else "Pending-reboot image profile -- not assessed; no esxcli software "
        "profile get --rebooting-image data found in this bundle"
    )
    has_memory_health_data = any(h.memory_health_data_available for h in assessment.hosts)
    memory_health_item = (
        "Memory (ECC hardware and reservation admission-control) health, per ESXi's "
        "own built-in healthd check (vmw.memoryHealth)"
        if has_memory_health_data
        else "Memory health -- not assessed; no vmw.memoryHealth healthd data found "
        "in this bundle"
    )
    log_window_label = _log_window_label(assessment)
    if vcenter is None:
        return (
            "ESXi host status and diagnostic data availability",
            "Storage device, adapter, SMART, and multipath path-state health",
            "Hardware sensor status (IPMI)",
            "Storage-related log signals (PDL/APD/ALUA/VOB), scoped to the last "
            f"{log_window_label}",
            "Server and CPU hardware inventory, including processor compatibility "
            "across hosts",
            "Cluster/compute-resource membership, where host-reported in the bundle",
            ntp_item,
            coredump_item,
            vib_item,
            configstore_item,
            network_item,
            mobility_item,
            pending_reboot_item,
            memory_health_item,
            evc_item,
            datastore_item,
            vm_item,
            f"vCenter-level active alarms -- not assessed; {_VCENTER_BUNDLE_REQUIRED}",
        )
    items = [
        "ESXi host status and diagnostic data availability",
        "Storage device, adapter, SMART, and multipath path-state health",
        "Hardware sensor status (IPMI)",
        f"Storage-related log signals (PDL/APD/ALUA/VOB), scoped to the last {log_window_label}",
        "Server and CPU hardware inventory, including processor compatibility across hosts",
        "vCenter Server appliance status: version, service-control service status and "
        f"appliance filesystem usage (vCenter bundle for {vcenter.hostname})",
        "Cluster inventory: cluster names and member hosts, as recovered from the "
        "vCenter operational logs in the capture",
        ntp_item,
        coredump_item,
        vib_item,
        configstore_item,
        network_item,
        mobility_item,
        pending_reboot_item,
        memory_health_item,
        evc_item,
        datastore_item,
        vm_item,
        f"vCenter-level active alarms -- {_VCENTER_DB_NOT_PARSED}",
    ]
    return tuple(items)


_DEFAULT_LOG_WINDOW_WEEKS = 13


def _log_window_label(assessment: Assessment) -> str:
    """"N week(s) (M days)" for whichever log-signal lookback window was

    actually used for this assessment's hosts (set once per assessment
    from ``AssessmentConfig.log_window_weeks`` / ``vhealth assess
    --weeks`` before parsing began -- uniform across every host in one
    assessment, so the first host's value is representative). Falls back
    to this tool's own default when there are no hosts to read it from.
    """
    weeks = next(
        (h.log_window_weeks for h in assessment.hosts), _DEFAULT_LOG_WINDOW_WEEKS
    )
    return f"{weeks} week(s) ({weeks * 7} days)"


def _worst_severity(findings: list[Finding]) -> Severity | None:
    if not findings:
        return None
    return max((f.severity for f in findings), key=lambda s: s.rank)


def _status_label(worst: Severity | None) -> str:
    if worst is None:
        return "Healthy"
    if worst.rank >= Severity.HIGH.rank:
        return "Attention Needed"
    return "Advisory"


def _by_ids(findings: list[Finding], ids: set[str]) -> list[Finding]:
    return [f for f in findings if f.rule_id in ids]


@dataclass(frozen=True)
class ComponentStatus:
    component: str
    status: str
    remarks: str


def component_status_rows(assessment: Assessment) -> list[ComponentStatus]:
    hosts = assessment.hosts
    findings = assessment.findings
    total = len(hosts)
    rows: list[ComponentStatus] = []

    vc_findings = [f for f in findings if f.rule_id.startswith(_VCENTER_RULE_PREFIX)]
    if assessment.vcenter is None:
        rows.append(
            ComponentStatus(
                "vCenter Server",
                NOT_ASSESSED,
                f"vCenter Server appliance specifications and health {_VCENTER_BUNDLE_REQUIRED}",
            )
        )
    else:
        vcenter = assessment.vcenter
        stopped_count = len(vcenter.services_stopped)
        max_percent = max(
            (d.percent_used for d in vcenter.appliance_disks if d.percent_used is not None),
            default=None,
        )
        busiest = (
            max(
                vcenter.appliance_disks,
                key=lambda d: d.percent_used if d.percent_used is not None else -1,
            )
            if max_percent is not None
            else None
        )
        remark_bits = [f"vCenter bundle for {vcenter.hostname} present"]
        if vcenter.vc_version:
            remark_bits.append(f"version {vcenter.vc_version}")
        if vcenter.services_running and vcenter.services_stopped is not None:
            remark_bits.append(
                f"{len(vcenter.services_running)} service(s) running, {stopped_count} stopped "
                "at capture"
            )
        if busiest is not None:
            remark_bits.append(f"busiest appliance disk {busiest.mount} at {max_percent}% used")
        rows.append(
            ComponentStatus(
                "vCenter Server",
                _status_label(_worst_severity(vc_findings)),
                "; ".join(remark_bits) + ".",
            )
        )

    version_known = sum(1 for h in hosts if h.esxi_version)
    rows.append(
        ComponentStatus(
            "ESXi Hosts",
            "Healthy" if total and version_known == total else "Attention Needed",
            f"{version_known} of {total} host(s) returned ESXi version/build data.",
        )
    )

    rows.append(_cluster_status_row(assessment))

    all_vms = [vm for h in hosts for vm in h.virtual_machines]
    no_mask_vms = [vm for vm in all_vms if vm.no_evc_masks_observed]
    if no_mask_vms:
        evc_status = "Informational"
        evc_remark = (
            f"No EVC CPU-feature masking observed in {len(no_mask_vms)} of "
            f"{len(all_vms)} running VM(s)' own power-on log (vmware.log); this suggests "
            "EVC is not actively constraining CPU features right now. This is evidence "
            "from VM-level logs, not a read of the cluster's configured EVC baseline, "
            f"which {_VCENTER_DB_FIELDS_UNAVAILABLE}."
        )
    else:
        evc_status = NOT_ASSESSED
        evc_remark = (
            f"Cluster EVC baseline {_VCENTER_BUNDLE_REQUIRED}"
            if assessment.vcenter is None
            else f"Cluster EVC baseline -- {_VCENTER_DB_NOT_PARSED}"
        )
    rows.append(
        ComponentStatus(
            "EVC Mode",
            evc_status,
            evc_remark,
        )
    )

    cpu_findings = _by_ids(findings, _PROCESSOR_RULE_IDS)
    if cpu_findings:
        cpu_status = _status_label(_worst_severity(cpu_findings))
        cpu_remark = cpu_findings[0].summary
    else:
        known = sum(1 for h in hosts if h.cpu_model)
        cpu_status = "Healthy"
        cpu_remark = (
            f"{known} of {total} host(s) report a CPU model; no mismatch detected."
            if known
            else "CPU model not available from this bundle."
        )
    rows.append(ComponentStatus("Processor Compatibility", cpu_status, cpu_remark))

    hosts_with_datastores = [h for h in hosts if h.datastores]
    if hosts_with_datastores:
        datastore_names = {ds.name for h in hosts_with_datastores for ds in h.datastores}
        usage_findings = _by_ids(findings, _DATASTORE_USAGE_RULE_IDS)
        datastores_status = _status_label(_worst_severity(usage_findings)) or "Informational"
        datastores_remark = (
            f"{len(datastore_names)} distinct datastore name(s) identified from "
            f"{len(hosts_with_datastores)} of {total} host(s) (per-volume vmkfstools "
            "dumps), including each volume's own point-in-time capacity/free-space "
            "reading"
        )
        datastores_remark += (
            f"; {len(usage_findings)} nearing/at capacity -- see Recommendation."
            if usage_findings
            else "; none nearing capacity (vCenter's own 75%/85%-used thresholds)."
        )
        datastores_remark += (
            f" vCenter-side storage-policy compliance status {_VCENTER_DB_FIELDS_UNAVAILABLE}."
        )
    else:
        datastores_status = NOT_ASSESSED
        datastores_remark = (
            "Datastore names, capacity, and accessibility -- not assessed; no VMFS volume "
            "data (vmkfstools) found in this bundle."
        )
    rows.append(ComponentStatus("Datastores", datastores_status, datastores_remark))

    hosts_with_vms = [h for h in hosts if h.vm_inventory_available]
    if hosts_with_vms:
        running_vms = sum(len(h.virtual_machines) for h in hosts_with_vms)
        vms_status = "Informational"
        vms_remark = (
            f"{running_vms} running VM(s) observed across {len(hosts_with_vms)} of {total} "
            "host(s), from each host's own record of what it is currently running. "
            f"Powered-off VMs and resource-utilization history {_VCENTER_DB_FIELDS_UNAVAILABLE}."
        )
    else:
        vms_status = NOT_ASSESSED
        vms_remark = (
            "VM inventory -- not assessed; no running-VM data (localcli vm process list) "
            "found in this bundle."
        )
    rows.append(ComponentStatus("Virtual Machines", vms_status, vms_remark))

    hosts_with_ntp_data = [h for h in hosts if h.ntp_data_available]
    if hosts_with_ntp_data:
        not_synced = [h for h in hosts_with_ntp_data if h.ntp_time_synchronized is False]
        ntp_findings = _by_ids(findings, _NTP_RULE_IDS)
        ntp_status = _status_label(_worst_severity(ntp_findings)) if ntp_findings else "Healthy"
        if not_synced:
            ntp_remark = (
                f"{len(not_synced)} of {len(hosts_with_ntp_data)} host(s) with NTP data "
                f"report 'Time Synchronized' = false: "
                f"{', '.join(h.hostname for h in not_synced)}."
            )
        else:
            ntp_remark = (
                f"All {len(hosts_with_ntp_data)} of {total} host(s) with NTP data report "
                "their clock as synchronized."
            )
    else:
        ntp_status = NOT_ASSESSED
        ntp_remark = (
            "Time synchronization -- not assessed; no NTP data (esxcli system ntp get) "
            "found in this bundle."
        )
    rows.append(ComponentStatus("Time Synchronization (NTP)", ntp_status, ntp_remark))

    hosts_with_coredump_data = [h for h in hosts if h.coredump_data_available]
    if hosts_with_coredump_data:
        not_configured = [h for h in hosts_with_coredump_data if h.coredump_configured is False]
        coredump_findings = _by_ids(findings, _COREDUMP_RULE_IDS)
        coredump_status = (
            _status_label(_worst_severity(coredump_findings)) if coredump_findings else "Healthy"
        )
        if not_configured:
            coredump_remark = (
                f"{len(not_configured)} of {len(hosts_with_coredump_data)} host(s) with "
                "coredump data have no active/configured coredump target: "
                f"{', '.join(h.hostname for h in not_configured)}."
            )
        else:
            coredump_remark = (
                f"All {len(hosts_with_coredump_data)} of {total} host(s) with coredump "
                "data have an active, configured kernel-coredump target."
            )
    else:
        coredump_status = NOT_ASSESSED
        coredump_remark = (
            "Kernel-coredump target configuration -- not assessed; no coredump data "
            "(esxcli system coredump file list) found in this bundle."
        )
    rows.append(
        ComponentStatus("Kernel Coredump Configuration", coredump_status, coredump_remark)
    )

    hosts_with_vib_data = [h for h in hosts if h.vib_data_available]
    if hosts_with_vib_data:
        hosts_with_community_vibs = [h for h in hosts_with_vib_data if h.community_supported_vibs]
        vib_findings = _by_ids(findings, _VIB_RULE_IDS)
        vib_status = _status_label(_worst_severity(vib_findings)) if vib_findings else "Healthy"
        if hosts_with_community_vibs:
            vib_remark = (
                f"{len(hosts_with_community_vibs)} of {len(hosts_with_vib_data)} host(s) "
                "with VIB data have at least one CommunitySupported (unsupported) VIB "
                f"installed: {', '.join(h.hostname for h in hosts_with_community_vibs)}."
            )
        else:
            vib_remark = (
                f"All {len(hosts_with_vib_data)} of {total} host(s) with VIB data have no "
                "CommunitySupported VIBs installed."
            )
    else:
        vib_status = NOT_ASSESSED
        vib_remark = (
            "Installed VIB acceptance levels -- not assessed; no VIB data (esxcli "
            "software vib list) found in this bundle."
        )
    rows.append(ComponentStatus("VIB Acceptance Level", vib_status, vib_remark))

    hosts_with_configstore_data = [h for h in hosts if h.configstore_data_available]
    if hosts_with_configstore_data:
        failed = [h for h in hosts_with_configstore_data if h.configstore_integrity_ok is False]
        configstore_findings = _by_ids(findings, _CONFIGSTORE_RULE_IDS)
        configstore_status = (
            _status_label(_worst_severity(configstore_findings))
            if configstore_findings
            else "Healthy"
        )
        if failed:
            configstore_remark = (
                f"{len(failed)} of {len(hosts_with_configstore_data)} host(s) failed "
                f"their ConfigStore integrity check: {', '.join(h.hostname for h in failed)}."
            )
        else:
            configstore_remark = (
                f"All {len(hosts_with_configstore_data)} of {total} host(s) with "
                "ConfigStore data report 'ok' on their integrity check."
            )
    else:
        configstore_status = NOT_ASSESSED
        configstore_remark = (
            "ConfigStore database integrity -- not assessed; no sqlite3 "
            "PRAGMA integrity_check data found in this bundle."
        )
    rows.append(ComponentStatus("ConfigStore Integrity", configstore_status, configstore_remark))

    hosts_with_mobility_data = [h for h in hosts if h.mobility_data_available]
    if hosts_with_mobility_data:
        mobility_findings = _by_ids(findings, _MOBILITY_RULE_IDS)
        mobility_status = (
            _status_label(_worst_severity(mobility_findings)) if mobility_findings else "Healthy"
        )
        if mobility_findings:
            affected_services = sorted(
                {f.affected_object for f in mobility_findings if f.affected_object}
            )
            mobility_remark = (
                f"{len(mobility_findings)} migration-network health check ERROR(s) "
                f"reported by ESXi's own tool, across {len(hosts_with_mobility_data)} "
                f"of {total} host(s) with data: {', '.join(affected_services)}."
            )
        else:
            mobility_remark = (
                f"All {len(hosts_with_mobility_data)} of {total} host(s) with migration-"
                "network health check data report no ERROR status."
            )
    else:
        mobility_status = NOT_ASSESSED
        mobility_remark = (
            "Migration-network (vMotion/Provisioning) health check -- not assessed; "
            "no mobility_network_health_check data found in this bundle (the tool "
            "itself fails to run on some ESXi builds/configurations)."
        )
    rows.append(
        ComponentStatus("Migration Network Health", mobility_status, mobility_remark)
    )

    hosts_with_pending_reboot_data = [h for h in hosts if h.pending_reboot_data_available]
    if hosts_with_pending_reboot_data:
        pending = [h for h in hosts_with_pending_reboot_data if h.pending_reboot_image_name]
        pending_reboot_findings = _by_ids(findings, _PENDING_REBOOT_RULE_IDS)
        pending_reboot_status = (
            _status_label(_worst_severity(pending_reboot_findings))
            if pending_reboot_findings
            else "Healthy"
        )
        if pending:
            pending_reboot_remark = (
                f"{len(pending)} of {len(hosts_with_pending_reboot_data)} host(s) have an "
                f"image profile staged but not yet applied by a reboot: "
                f"{', '.join(h.hostname for h in pending)}."
            )
        else:
            pending_reboot_remark = (
                f"All {len(hosts_with_pending_reboot_data)} of {total} host(s) with "
                "pending-reboot data have no image profile staged."
            )
    else:
        pending_reboot_status = NOT_ASSESSED
        pending_reboot_remark = (
            "Pending-reboot image profile -- not assessed; no esxcli software profile "
            "get --rebooting-image data found in this bundle."
        )
    rows.append(
        ComponentStatus(
            "Pending Reboot (Image Profile)", pending_reboot_status, pending_reboot_remark
        )
    )

    hosts_with_memory_health_data = [h for h in hosts if h.memory_health_data_available]
    if hosts_with_memory_health_data:
        degraded = [
            h
            for h in hosts_with_memory_health_data
            if h.memory_hardware_state not in (None, "Green")
            or h.memory_reservation_state not in (None, "Green")
        ]
        memory_health_findings = _by_ids(findings, _MEMORY_RULE_IDS)
        memory_health_status = (
            _status_label(_worst_severity(memory_health_findings))
            if memory_health_findings
            else "Healthy"
        )
        if degraded:
            memory_health_remark = (
                f"{len(degraded)} of {len(hosts_with_memory_health_data)} host(s) report a "
                f"non-'Green' memory hardware or reservation state: "
                f"{', '.join(h.hostname for h in degraded)}."
            )
        else:
            memory_health_remark = (
                f"All {len(hosts_with_memory_health_data)} of {total} host(s) with "
                "memory-health data report 'Green' hardware and reservation state."
            )
    else:
        memory_health_status = NOT_ASSESSED
        memory_health_remark = (
            "Memory health -- not assessed; no vmw.memoryHealth healthd data found "
            "in this bundle."
        )
    rows.append(ComponentStatus("Memory Health", memory_health_status, memory_health_remark))

    hosts_with_switch_data = [h for h in hosts if h.network_switch_data_available]
    if hosts_with_switch_data:
        network_findings = _by_ids(findings, _NETWORK_RULE_IDS)
        network_status = (
            _status_label(_worst_severity(network_findings)) if network_findings else "Healthy"
        )
        single_uplink_count = sum(
            1 for f in network_findings if f.rule_id == "network.vswitch_single_uplink"
        )
        link_down_count = sum(
            1
            for f in network_findings
            if f.rule_id in ("network.vswitch_uplink_link_down", "network.vswitch_all_uplinks_down")
        )
        mtu_mismatch_count = sum(
            1 for f in network_findings if f.rule_id == "fleet.vswitch_mtu_mismatch"
        )
        if network_findings:
            bits = []
            if single_uplink_count:
                bits.append(f"{single_uplink_count} switch(es) with only one uplink")
            if link_down_count:
                bits.append(
                    f"{link_down_count} switch(es) with a configured uplink that has no "
                    "physical link"
                )
            if mtu_mismatch_count:
                bits.append(f"{mtu_mismatch_count} switch(es) with inconsistent MTU across hosts")
            network_remark = "; ".join(bits) + "."
        else:
            total_switches = sum(len(h.network_switches) for h in hosts_with_switch_data)
            network_remark = (
                f"{total_switches} vSwitch/DVS instance(s) identified across "
                f"{len(hosts_with_switch_data)} of {total} host(s); no single-uplink or "
                "cross-host MTU-mismatch issues detected."
            )
    else:
        network_status = NOT_ASSESSED
        network_remark = (
            "vSwitch/DVS configuration -- not assessed; no esxcfg-vswitch -l data found "
            "in this bundle."
        )
    rows.append(ComponentStatus("Network (vSwitch/DVS)", network_status, network_remark))

    storage_hw_findings = _by_ids(findings, _STORAGE_HARDWARE_RULE_IDS)
    rows.append(
        ComponentStatus(
            "Storage & Hardware Findings",
            _status_label(_worst_severity(storage_hw_findings)),
            f"{len(storage_hw_findings)} finding(s) in this assessment."
            if storage_hw_findings
            else "No storage, SMART, sensor, or log findings in this assessment.",
        )
    )

    overall = _status_label(_worst_severity(findings))
    rows.append(
        ComponentStatus(
            "Overall",
            overall,
            "Stable; see recommendations for any remediation items."
            if overall != "Attention Needed"
            else f"{len(findings)} finding(s) across {total} host(s) require remediation.",
        )
    )
    return rows


def _cluster_status_row(assessment: Assessment) -> ComponentStatus:
    """Build the Cluster Status row from all available evidence.

    Preference order per host: (1) the resolved cluster display name from
    the vCenter Server bundle (log-derived moref->name mapping), (2) the
    host-reported cluster/compute-resource ID. Hosts reporting no cluster
    are counted as standalone.
    """
    hosts = assessment.hosts
    total = len(hosts)
    # Reverse mapping (name -> moref), so every host sharing a resolved
    # cluster name gets an identical label -- whether or not *that* host
    # happened to self-report a cluster_id -- instead of being split into
    # a second, moref-less group next to the one that did.
    moref_by_name: dict[str, str] = {}
    if assessment.vcenter is not None:
        for moref, name in assessment.vcenter.cluster_names.items():
            moref_by_name.setdefault(name, moref)
    clustered = [
        (h, _cluster_label(h, moref_by_name)) for h in hosts if h.cluster_id or h.cluster_name
    ]
    alarmed = [h for h in clustered if h[0].cluster_in_alarm]

    if not clustered:
        return ComponentStatus(
            "Cluster Status",
            "Informational",
            "No cluster-membership data found in this bundle."
            + (
                ""
                if assessment.vcenter is None
                else " The vCenter capture did not provide a readable cluster inventory."
            ),
        )

    by_label: dict[str, list[str]] = {}
    for host, label in clustered:
        by_label.setdefault(label, []).append(host.hostname)

    parts = []
    for label in sorted(by_label):
        members = sorted(set(by_label[label]))
        preview = ", ".join(members[:3])
        suffix = "..." if len(members) > 3 else ""
        parts.append(f"{label}: {len(members)} host(s) ({preview}{suffix})")
    remark = "; ".join(parts) + "."
    standalone = total - len(clustered)
    if standalone:
        remark += f" {standalone} of {total} host(s) report no cluster membership (standalone)."
    if alarmed:
        remark += f" {len(alarmed)} host(s) report a local cluster-agent alarm."
    return ComponentStatus("Cluster Status", "Informational" if not alarmed else "Advisory", remark)


def _cluster_label(host: HostInfo, moref_by_name: dict[str, str]) -> str | None:
    """A cluster label for this host's reported membership, if any.

    Prefers the resolved cluster display name from the vCenter bundle --
    available even when the host itself never reported a cluster ID, since
    it can also be resolved from vCenter-side cluster membership -- and
    otherwise falls back to the raw host-reported ID. The moref shown
    alongside the name always comes from the vCenter bundle's own mapping
    (``moref_by_name``), not from this particular host's self-reported
    ``cluster_id``, so every host resolved to the same cluster name is
    grouped under one identical label.
    """
    if host.cluster_name:
        moref = moref_by_name.get(host.cluster_name) or (
            host.cluster_id.rsplit(":", 1)[-1] if host.cluster_id else None
        )
        return f"{host.cluster_name} ({moref})" if moref else host.cluster_name
    return host.cluster_id


def key_findings_at_a_glance(assessment: Assessment) -> list[str]:
    rows = component_status_rows(assessment)
    overall = next(r for r in rows if r.component == "Overall")
    overall_phrase = (
        "operational and healthy"
        if overall.status == "Healthy"
        else "operational, with findings that need attention"
    )
    items = [f"The assessed environment is {overall_phrase}."]

    cpu_row = next(r for r in rows if r.component == "Processor Compatibility")
    if cpu_row.status != "Healthy":
        items.append(f"{cpu_row.remarks} -- action recommended.")

    storage_row = next(r for r in rows if r.component == "Storage & Hardware Findings")
    if storage_row.status == "Attention Needed":
        items.append(
            f"{storage_row.remarks} High/critical-severity items should be reviewed first."
        )
    else:
        items.append("No critical or high-severity storage/hardware findings in this assessment.")

    datastores_row = next(r for r in rows if r.component == "Datastores")
    vms_row = next(r for r in rows if r.component == "Virtual Machines")
    if datastores_row.status != NOT_ASSESSED or vms_row.status != NOT_ASSESSED:
        items.append(f"{datastores_row.remarks}")
        items.append(f"{vms_row.remarks}")
    else:
        items.append(
            "Datastore and virtual machine data were not assessed from this bundle "
            "(see Scope of Health Check)."
        )
    ntp_row = next(r for r in rows if r.component == "Time Synchronization (NTP)")
    if ntp_row.status != NOT_ASSESSED:
        items.append(ntp_row.remarks)

    coredump_row = next(r for r in rows if r.component == "Kernel Coredump Configuration")
    if coredump_row.status != NOT_ASSESSED:
        items.append(coredump_row.remarks)

    vib_row = next(r for r in rows if r.component == "VIB Acceptance Level")
    if vib_row.status != NOT_ASSESSED:
        items.append(vib_row.remarks)

    network_row = next(r for r in rows if r.component == "Network (vSwitch/DVS)")
    if network_row.status != NOT_ASSESSED:
        items.append(network_row.remarks)

    evc_row = next(r for r in rows if r.component == "EVC Mode")
    if evc_row.status != NOT_ASSESSED:
        items.append(evc_row.remarks)
    elif assessment.vcenter is None:
        items.append(
            "EVC mode and vCenter-level alarm data were not assessed from this bundle type "
            "(see Scope of Health Check)."
        )
    else:
        items.append(
            "The vCenter Server appliance was captured in the bundle and its service status, "
            "appliance disk usage and cluster information were reviewed; EVC mode and "
            "vCenter-level alarm data require vCenter database content and remain not "
            "assessed (see Scope of Health Check)."
        )
    return items


@dataclass(frozen=True)
class HardwareStatusGrid:
    hw_disk: str
    management_connection: str
    health: str
    power: str
    observations: str


def hardware_status_grid(assessment: Assessment) -> HardwareStatusGrid:
    findings = assessment.findings
    disk_status = _status_label(
        _worst_severity(
            _by_ids(
                findings,
                _DEVICE_HEALTH_RULE_IDS | _LOG_SIGNAL_RULE_IDS | _MULTIPATH_RULE_IDS,
            )
        )
    )
    sensor_status = _status_label(_worst_severity(_by_ids(findings, _SENSOR_RULE_IDS)))

    urgent = [f for f in findings if f.severity.rank >= Severity.HIGH.rank]
    observations = (
        "No critical or high-severity findings observed in this assessment."
        if not urgent
        else f"{len(urgent)} critical/high-severity finding(s) observed in this "
        "assessment; see Recommendation."
    )

    return HardwareStatusGrid(
        hw_disk=disk_status,
        management_connection=NOT_ASSESSED,
        health=sensor_status,
        power=sensor_status,
        observations=observations,
    )


@dataclass(frozen=True)
class HostInventoryRow:
    index: int
    hostname: str
    management_ip: str
    server_model: str
    cpu_model: str


def host_inventory_rows(assessment: Assessment) -> list[HostInventoryRow]:
    rows = []
    for i, host in enumerate(sorted(assessment.hosts, key=lambda h: h.hostname), start=1):
        rows.append(
            HostInventoryRow(
                index=i,
                hostname=host.hostname,
                management_ip=host.management_ip or "unknown",
                server_model=(
                    f"{host.server_manufacturer} {host.server_model}".strip()
                    if host.server_manufacturer and host.server_model
                    else (host.server_model or "unknown")
                ),
                cpu_model=host.cpu_model or "unknown",
            )
        )
    return rows


@dataclass(frozen=True)
class VirtualMachineRow:
    index: int
    name: str
    host: str
    datastore: str
    uuid: str


def virtual_machine_inventory_rows(assessment: Assessment) -> list[VirtualMachineRow]:
    """Running VMs across all hosts, sorted by name -- see Datastores/Virtual

    Machines component rows for the "powered-on only" caveat this table
    inherits from its source (``localcli vm process list``).
    """
    entries = [
        (host, vm)
        for host in assessment.hosts
        for vm in host.virtual_machines
    ]
    entries.sort(key=lambda pair: pair[1].name)
    return [
        VirtualMachineRow(
            index=i,
            name=vm.name,
            host=host.hostname,
            datastore=host.datastore_name_for_uuid(vm.datastore_uuid) or "unknown",
            uuid=vm.uuid or "unknown",
        )
        for i, (host, vm) in enumerate(entries, start=1)
    ]


def detailed_observations(assessment: Assessment) -> list[str]:
    hosts = assessment.hosts
    total = len(hosts)
    findings = assessment.findings
    items: list[str] = []

    version_known = sum(1 for h in hosts if h.esxi_version)
    items.append(f"{version_known} of {total} ESXi host(s) returned version/build data.")

    cluster_hosts = [h for h in hosts if h.cluster_id]
    if cluster_hosts:
        named = [h for h in cluster_hosts if h.cluster_name]
        if named:
            names = sorted({f"{h.cluster_name} ({h.cluster_id.rsplit(':', 1)[-1]})" for h in named})
            items.append(
                f"{len(named)} of {total} host(s) have their cluster identified in the "
                f"vCenter capture: {', '.join(names)}; this is host/vCenter-reported "
                "membership, not a full read of the vCenter inventory."
            )
        else:
            items.append(
                f"{len(cluster_hosts)} of {total} host(s) report a compute-resource/cluster ID "
                "locally; the cluster display name is not available from the supplied "
                "capture, so the raw IDs are shown."
            )

    cpu_findings = _by_ids(findings, _PROCESSOR_RULE_IDS)
    if cpu_findings:
        items.append(cpu_findings[0].summary)
    else:
        items.append("No processor-compatibility mismatch detected across assessed hosts.")

    storage_hw = _by_ids(findings, _STORAGE_HARDWARE_RULE_IDS)
    window_label = _log_window_label(assessment)
    if storage_hw:
        items.append(
            f"{len(storage_hw)} storage/hardware finding(s) were observed within the "
            f"last {window_label} (for log-based signals) or at capture time (for "
            "device/sensor snapshots); see Recommendation."
        )
    else:
        items.append(
            f"No storage or hardware findings were observed within the last {window_label}."
        )

    ntp_hosts = [h for h in hosts if h.ntp_data_available]
    if ntp_hosts:
        not_synced = sum(1 for h in ntp_hosts if h.ntp_time_synchronized is False)
        items.append(
            f"{len(ntp_hosts) - not_synced} of {len(ntp_hosts)} host(s) with NTP data report "
            "their clock as synchronized."
        )

    coredump_hosts = [h for h in hosts if h.coredump_data_available]
    if coredump_hosts:
        not_configured = sum(1 for h in coredump_hosts if h.coredump_configured is False)
        items.append(
            f"{len(coredump_hosts) - not_configured} of {len(coredump_hosts)} host(s) with "
            "coredump data have an active, configured kernel-coredump target."
        )

    vib_hosts = [h for h in hosts if h.vib_data_available]
    if vib_hosts:
        with_community_vibs = sum(1 for h in vib_hosts if h.community_supported_vibs)
        items.append(
            f"{len(vib_hosts) - with_community_vibs} of {len(vib_hosts)} host(s) with VIB "
            "data have no CommunitySupported VIBs installed."
        )

    switch_hosts = [h for h in hosts if h.network_switch_data_available]
    if switch_hosts:
        network_findings = _by_ids(findings, _NETWORK_RULE_IDS)
        if network_findings:
            items.append(
                f"{len(network_findings)} vSwitch/DVS finding(s) (single-uplink, "
                "configured-but-no-link uplink, and/or cross-host MTU mismatch) "
                "observed; see Recommendation."
            )
        else:
            items.append(
                f"{len(switch_hosts)} of {total} host(s) with vSwitch/DVS data show no "
                "single-uplink or cross-host MTU-mismatch issues."
            )

    return items


# Which domain each rule belongs to, for grouping/reading the Recommendation
# section by subsystem rather than as one flat list. Every rule_id must have
# an entry here -- CONTRIBUTING.md's "add a rule" checklist includes adding
# one.
_CATEGORY_BY_RULE_ID = {
    "storage.smart_health_not_ok": "Storage",
    "storage.smart_reallocated_sectors": "Storage",
    "storage.device_not_on": "Storage",
    "storage.pdl_detected": "Storage",
    "storage.apd_detected": "Storage",
    "storage.path_dead_detected": "Storage",
    "storage.alua_path_connectivity": "Storage",
    "storage.vob_problem_event": "Storage",
    "hardware.ipmi_sensor_asserted": "Hardware / SEL",
    "hardware.sel_ecc_uncorrectable": "Hardware / SEL",
    "hardware.sel_drive_predictive_failure": "Hardware / SEL",
    "hardware.sel_psu_failure": "Hardware / SEL",
    "hardware.sel_temperature_critical": "Hardware / SEL",
    "fleet.cpu_model_mismatch": "CPU",
    "hardware.ntp_not_synchronized": "Other",
    "hardware.coredump_not_configured": "Other",
    "hardware.community_supported_vib_installed": "Other",
    "hardware.configstore_integrity_check_failed": "Other",
    "hardware.pending_reboot_image": "Other",
    "hardware.memory_hardware_health_degraded": "Memory",
    "hardware.memory_reservation_health_degraded": "Memory",
    "storage.multipath_all_paths_dead": "Storage",
    "storage.multipath_reduced_redundancy": "Storage",
    "network.vswitch_single_uplink": "Network",
    "network.vswitch_uplink_link_down": "Network",
    "network.vswitch_all_uplinks_down": "Network",
    "network.mobility_health_check_error": "Network",
    "fleet.vswitch_mtu_mismatch": "Network",
    "fleet.datastore_usage_warning": "Storage",
    "fleet.datastore_usage_critical": "Storage",
    "coverage.limited_diagnostic_data": "Other",
    "vcenter.core_service_stopped": "vCenter",
    "vcenter.optional_service_stopped": "vCenter",
    "vcenter.appliance_disk_usage": "vCenter",
}
_DEFAULT_CATEGORY = "Other"
_MAX_EVIDENCE_LINES_PER_GROUP = 5

# Reader-friendly category order for the detailed findings log (see
# ``findings_by_category`` below) -- storage and network issues are the
# ones an engineer most often needs to act on first, "Other" always last.
CATEGORY_DISPLAY_ORDER = [
    "Storage",
    "Network",
    "Hardware / SEL",
    "Memory",
    "CPU",
    "vCenter",
    "Other",
]


def category_for_rule_id(rule_id: str) -> str:
    return _CATEGORY_BY_RULE_ID.get(rule_id, _DEFAULT_CATEGORY)


def findings_by_category(assessment: Assessment) -> list[tuple[str, list[Finding]]]:
    """Group every raised finding by rule category, worst-severity-first within

    each group, in ``CATEGORY_DISPLAY_ORDER``. Used by the companion detailed
    findings log so a reader can jump straight to "Storage" or "Network"
    instead of scanning one flat list sorted only by severity; the main
    report's grouped Recommendation section already shows category per item
    and is left as-is.
    """
    by_category: dict[str, list[Finding]] = {}
    for finding in assessment.findings:
        by_category.setdefault(category_for_rule_id(finding.rule_id), []).append(finding)
    for findings in by_category.values():
        findings.sort(key=lambda f: -f.severity.rank)
    ordered = [c for c in CATEGORY_DISPLAY_ORDER if c in by_category]
    ordered += sorted(c for c in by_category if c not in CATEGORY_DISPLAY_ORDER)
    return [(c, by_category[c]) for c in ordered]


@dataclass(frozen=True)
class RecommendationGroup:
    title: str
    category: str
    severity: str
    affected: list[str]
    action: str
    limitations: str | None
    evidence: list[str]


def recommendation_groups(assessment: Assessment) -> list[RecommendationGroup]:
    by_rule: dict[str, list[Finding]] = {}
    for finding in assessment.findings:
        by_rule.setdefault(finding.rule_id, []).append(finding)

    groups = []
    for items in by_rule.values():
        worst = _worst_severity(items)
        affected = sorted({f.affected_host for f in items if f.affected_host})
        action = next((f.remediation for f in items if f.remediation), None)
        limitations = next((f.limitations for f in items if f.limitations), None)
        evidence: list[str] = []
        for finding in items:
            for line in finding.evidence:
                tagged = f"{finding.affected_host}: {line}" if finding.affected_host else line
                if tagged not in evidence:
                    evidence.append(tagged)
                if len(evidence) >= _MAX_EVIDENCE_LINES_PER_GROUP:
                    break
            if len(evidence) >= _MAX_EVIDENCE_LINES_PER_GROUP:
                break
        groups.append(
            RecommendationGroup(
                title=items[0].title,
                category=_CATEGORY_BY_RULE_ID.get(items[0].rule_id, _DEFAULT_CATEGORY),
                severity=worst.value if worst else "info",
                affected=affected or ["(fleet-wide)"],
                action=action or "Review the finding details for this check.",
                limitations=limitations,
                evidence=evidence,
            )
        )
    groups.sort(key=lambda g: -Severity(g.severity).rank)
    return groups


def executive_summary_text(assessment: Assessment) -> str:
    hosts = len(assessment.hosts)
    findings = assessment.findings
    urgent = sum(1 for f in findings if f.severity.rank >= Severity.HIGH.rank)
    other = len(findings) - urgent

    if not findings:
        outcome = "No findings were raised by the checks that could run against this bundle."
    elif urgent:
        outcome = (
            f"{urgent} critical/high-severity finding(s) require attention; "
            f"{other} additional finding(s) are medium, low, or informational."
        )
    else:
        outcome = (
            f"All {other} finding(s) raised are medium, low, or informational; no critical "
            "or high-severity issues were found."
        )

    vcenter_bit = ""
    if assessment.vcenter is not None:
        vcenter_bit = (
            f" The supplied bundle also includes the vCenter Server appliance "
            f"({assessment.vcenter.hostname}) capture, which was reviewed for appliance "
            "service status, disk usage and cluster information."
        )
    window_label = _log_window_label(assessment)
    return (
        f"This quarterly health check assessment was performed on the customer's VMware "
        f"vSphere environment, covering {hosts} ESXi host(s), to evaluate overall operational "
        f"status and identify any issues affecting stability or availability within the last "
        f"{window_label}.{vcenter_bit} {outcome} Recommendations are provided in Section 3.4. A "
        f"separate detailed findings log accompanies this report; see Section 2 for what "
        f"this assessment could and could not check from the supplied bundle."
    )
