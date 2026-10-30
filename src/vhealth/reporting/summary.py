"""Pure data-shaping helpers shared by the DOCX and HTML report renderers.

Keeps the aggregation/judgement logic -- what counts as "Healthy" vs
"Attention Needed", which findings belong to which component bucket --
in one place, tested once, instead of duplicated between two template
engines. Nothing here reaches outside the already-computed ``Assessment``;
it only reshapes it for display.
"""

from __future__ import annotations

from dataclasses import dataclass

from vhealth.models.assessment import Assessment
from vhealth.models.findings import Finding, Severity

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
_SENSOR_RULE_IDS = {"hardware.ipmi_sensor_asserted"}
_PROCESSOR_RULE_IDS = {"fleet.cpu_model_mismatch"}

NOT_ASSESSED = "Not assessed"

SCOPE_CHECKED = (
    "ESXi host identity and version/build (vm-support README, system-version-get)",
    "Storage HBA/controller and device/LUN inventory (esxcli storage core)",
    "SMART disk health, for devices whose driver exposes it to ESXi",
    "IPMI hardware sensors (fans, temperature, voltage, power supplies)",
    "vmkwarning/vobd log signals: PDL, APD, dead paths, ALUA, VOB storage events",
    "Server and CPU model identity (SMBIOS), and CPU-model consistency across hosts",
    "Host-reported cluster/compute-resource membership, where present in the bundle",
)

SCOPE_NOT_ASSESSED = (
    "EVC (Enhanced vMotion Compatibility) mode -- a vCenter cluster setting, not "
    "stored on the ESXi host itself",
    "vSphere HA / DRS configuration and admission control",
    "vCenter-level active alarms and events",
    "Virtual machine inventory, power state, or resource utilization (CPU/memory/disk)",
    "Datastore capacity, accessibility, or vSAN health",
    "Live connectivity to vCenter or any ESXi host -- this tool never connects to one",
)


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

    version_known = sum(1 for h in hosts if h.esxi_version)
    rows.append(
        ComponentStatus(
            "ESXi Hosts",
            "Healthy" if total and version_known == total else "Attention Needed",
            f"{version_known} of {total} host(s) returned ESXi version/build data.",
        )
    )

    device_findings = _by_ids(findings, _DEVICE_HEALTH_RULE_IDS)
    rows.append(
        ComponentStatus(
            "Storage Devices & SMART Health",
            _status_label(_worst_severity(device_findings)),
            f"{len(device_findings)} finding(s)."
            if device_findings
            else "No storage/SMART health findings.",
        )
    )

    log_findings = _by_ids(findings, _LOG_SIGNAL_RULE_IDS)
    rows.append(
        ComponentStatus(
            "Storage Log Signals (PDL/APD/ALUA/VOB)",
            _status_label(_worst_severity(log_findings)),
            f"{len(log_findings)} finding(s)."
            if log_findings
            else "No storage path/log signal findings.",
        )
    )

    sensor_findings = _by_ids(findings, _SENSOR_RULE_IDS)
    rows.append(
        ComponentStatus(
            "Hardware Sensors (IPMI)",
            _status_label(_worst_severity(sensor_findings)),
            f"{len(sensor_findings)} finding(s)."
            if sensor_findings
            else "No asserted hardware sensors.",
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

    cluster_known = [h for h in hosts if h.cluster_id]
    rows.append(
        ComponentStatus(
            "Cluster Membership (host-reported)",
            "Informational",
            f"{len(cluster_known)} of {total} host(s) report a compute-resource/cluster ID "
            "locally (see host inventory)."
            if cluster_known
            else "No host-level cluster-membership data found in this bundle.",
        )
    )

    rows.append(
        ComponentStatus(
            "EVC Mode",
            NOT_ASSESSED,
            "Requires vCenter cluster configuration; not present in ESXi host-level "
            "support bundles.",
        )
    )
    rows.append(
        ComponentStatus(
            "vCenter Active Alarms / VM Resource Alerts",
            NOT_ASSESSED,
            "Requires a live vCenter connection or a vCenter-side export; not available "
            "from per-host ESXi bundles.",
        )
    )

    overall = _status_label(_worst_severity(findings))
    rows.append(
        ComponentStatus(
            "Overall (from checks performed)",
            overall,
            f"{len(findings)} finding(s) across {total} host(s) from the checks that could run.",
        )
    )
    return rows


@dataclass(frozen=True)
class HardwareStatusRow:
    label: str
    status: str


def hardware_status_rows(assessment: Assessment) -> list[HardwareStatusRow]:
    findings = assessment.findings
    disk_status = _status_label(
        _worst_severity(_by_ids(findings, _DEVICE_HEALTH_RULE_IDS | _LOG_SIGNAL_RULE_IDS))
    )
    sensor_status = _status_label(_worst_severity(_by_ids(findings, _SENSOR_RULE_IDS)))
    return [
        HardwareStatusRow("HW / Disk", disk_status),
        HardwareStatusRow("Management Connection Status", NOT_ASSESSED),
        HardwareStatusRow("Health (Hardware Sensors)", sensor_status),
        HardwareStatusRow("Power", sensor_status),
    ]


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
class RecommendationGroup:
    title: str
    severity: str
    affected: list[str]
    action: str
    limitations: str | None


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
        groups.append(
            RecommendationGroup(
                title=items[0].title,
                severity=worst.value if worst else "info",
                affected=affected or ["(fleet-wide)"],
                action=action or "Review the finding details for this check.",
                limitations=limitations,
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
        outcome = (
            "No findings were raised by the automated checks that could run against "
            "this bundle."
        )
    elif urgent:
        outcome = (
            f"{urgent} critical/high-severity finding(s) require attention; "
            f"{other} additional finding(s) are medium/low/informational."
        )
    else:
        outcome = (
            f"All {other} finding(s) raised are medium, low, or informational; no "
            "critical or high-severity issues were found."
        )

    return (
        f"This health check assessed {hosts} ESXi host(s) from the supplied diagnostic "
        f"bundle, entirely offline. {outcome} See Section 3 for the detailed breakdown "
        "and Section 3.5 for what this bundle type cannot be used to assess."
    )
