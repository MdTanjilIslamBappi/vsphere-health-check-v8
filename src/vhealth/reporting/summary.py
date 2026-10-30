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
_STORAGE_HARDWARE_RULE_IDS = _DEVICE_HEALTH_RULE_IDS | _LOG_SIGNAL_RULE_IDS | _SENSOR_RULE_IDS

NOT_ASSESSED = "Not assessed"
_VCENTER_DATA_REQUIRED = "requires vCenter-side data, which is not present in an ESXi host bundle."

SCOPE_ITEMS = (
    "ESXi host status and diagnostic data availability",
    "Storage device, adapter, and SMART health",
    "Hardware sensor status (IPMI)",
    "Storage-related log signals (PDL/APD/ALUA/VOB), scoped to the last 90 days",
    "Server and CPU hardware inventory, including processor compatibility across hosts",
    "Cluster/compute-resource membership, where host-reported in the bundle",
    f"Cluster EVC mode configuration -- not assessed; {_VCENTER_DATA_REQUIRED}",
    f"Datastore capacity and accessibility -- not assessed; {_VCENTER_DATA_REQUIRED}",
    f"Virtual machine inventory and resource utilization -- not assessed; {_VCENTER_DATA_REQUIRED}",
    f"vCenter-level active alarms -- not assessed; {_VCENTER_DATA_REQUIRED}",
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

    rows.append(
        ComponentStatus(
            "vCenter Server",
            NOT_ASSESSED,
            f"vCenter Server appliance specifications and health {_VCENTER_DATA_REQUIRED}",
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

    cluster_hosts = [h for h in hosts if h.cluster_id]
    alarmed = [h for h in cluster_hosts if h.cluster_in_alarm]
    if cluster_hosts:
        cluster_status = "Attention Needed" if alarmed else "Informational"
        cluster_remark = (
            f"{len(cluster_hosts)} of {total} host(s) report a compute-resource/cluster ID "
            "locally (see host inventory)."
        )
        if alarmed:
            cluster_remark += f" {len(alarmed)} host(s) report a local agent alarm."
    else:
        cluster_status = "Informational"
        cluster_remark = "No host-level cluster-membership data found in this bundle."
    rows.append(ComponentStatus("Cluster Status (host-reported)", cluster_status, cluster_remark))

    rows.append(
        ComponentStatus(
            "EVC Mode",
            NOT_ASSESSED,
            f"Cluster EVC baseline {_VCENTER_DATA_REQUIRED}",
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

    rows.append(
        ComponentStatus(
            "Datastores",
            NOT_ASSESSED,
            f"Datastore capacity and accessibility {_VCENTER_DATA_REQUIRED}",
        )
    )
    rows.append(
        ComponentStatus(
            "Virtual Machines",
            NOT_ASSESSED,
            f"VM inventory and resource utilization {_VCENTER_DATA_REQUIRED}",
        )
    )

    storage_hw_findings = _by_ids(findings, _STORAGE_HARDWARE_RULE_IDS)
    rows.append(
        ComponentStatus(
            "Storage & Hardware Findings",
            _status_label(_worst_severity(storage_hw_findings)),
            f"{len(storage_hw_findings)} finding(s) this quarter."
            if storage_hw_findings
            else "No storage, SMART, sensor, or log findings this quarter.",
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
        items.append("No critical or high-severity storage/hardware findings this quarter.")

    items.append(
        "EVC mode, datastore, virtual machine, and vCenter-level alarm data were not assessed "
        "from this bundle type (see Scope of Health Check)."
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
        _worst_severity(_by_ids(findings, _DEVICE_HEALTH_RULE_IDS | _LOG_SIGNAL_RULE_IDS))
    )
    sensor_status = _status_label(_worst_severity(_by_ids(findings, _SENSOR_RULE_IDS)))

    urgent = [f for f in findings if f.severity.rank >= Severity.HIGH.rank]
    observations = (
        "No critical or high-severity findings observed this quarter."
        if not urgent
        else f"{len(urgent)} critical/high-severity finding(s) observed this quarter; "
        "see Recommendation."
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


def detailed_observations(assessment: Assessment) -> list[str]:
    hosts = assessment.hosts
    total = len(hosts)
    findings = assessment.findings
    items: list[str] = []

    version_known = sum(1 for h in hosts if h.esxi_version)
    items.append(f"{version_known} of {total} ESXi host(s) returned version/build data.")

    cluster_hosts = [h for h in hosts if h.cluster_id]
    if cluster_hosts:
        items.append(
            f"{len(cluster_hosts)} of {total} host(s) report a compute-resource/cluster ID "
            "locally; this is host-reported data, not a read of vCenter's cluster "
            "configuration."
        )

    cpu_findings = _by_ids(findings, _PROCESSOR_RULE_IDS)
    if cpu_findings:
        items.append(cpu_findings[0].summary)
    else:
        items.append("No processor-compatibility mismatch detected across assessed hosts.")

    storage_hw = _by_ids(findings, _STORAGE_HARDWARE_RULE_IDS)
    if storage_hw:
        items.append(
            f"{len(storage_hw)} storage/hardware finding(s) were observed within the last "
            "90 days (this quarter); see Recommendation."
        )
    else:
        items.append("No storage or hardware findings were observed within the last 90 days.")

    return items


# Which domain each rule belongs to, for grouping/reading the Recommendation
# section by subsystem rather than as one flat list. Every rule_id must have
# an entry here -- CONTRIBUTING.md's "add a rule" checklist includes adding
# one. Categories not yet produced by any rule (Network, Memory) are kept
# available for rules added later.
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
    "fleet.cpu_model_mismatch": "CPU",
    "coverage.limited_diagnostic_data": "Other",
}
_DEFAULT_CATEGORY = "Other"
_MAX_EVIDENCE_LINES_PER_GROUP = 5


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

    return (
        f"This quarterly health check assessment was performed on the customer's VMware "
        f"vSphere environment, covering {hosts} ESXi host(s), to evaluate overall operational "
        f"status and identify any issues affecting stability or availability within the last "
        f"90 days. {outcome} Recommendations are provided in Section 3.4. A separate detailed "
        f"findings log accompanies this report; see Section 2 for what this assessment could "
        f"and could not check from the supplied bundle."
    )
