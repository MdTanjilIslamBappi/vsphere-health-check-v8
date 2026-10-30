"""Rules that compare data across every host in one assessment.

A single-host bundle never triggers these; they only fire when an
assessment covers more than one ESXi host (e.g. a vCenter-style bundle, or
several single-host bundles run together), since "compatibility" is a
fleet-wide question by definition.
"""

from __future__ import annotations

from collections import defaultdict

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import FleetRule


def _cpu_model_mismatch(hosts: list[HostInfo]) -> list[Finding]:
    by_model: dict[str, list[str]] = defaultdict(list)
    for host in hosts:
        if host.cpu_model:
            by_model[host.cpu_model].append(host.hostname)

    if len(by_model) < 2:
        return []

    evidence = [f"{model}: {', '.join(names)}" for model, names in sorted(by_model.items())]
    return [
        Finding(
            rule_id="fleet.cpu_model_mismatch",
            title="Multiple CPU models detected across assessed hosts",
            severity=Severity.MEDIUM,
            summary=(
                f"{len(by_model)} different CPU models were found across the "
                f"{sum(len(v) for v in by_model.values())} hosts in this assessment. Mixed CPU "
                "generations in the same vCenter cluster can block vMotion unless Enhanced "
                "vMotion Compatibility (EVC) is enabled with a baseline the oldest CPU supports."
            ),
            evidence=evidence,
            remediation=(
                "Confirm whether these hosts are in the same vCenter cluster. If so, enable an "
                "EVC baseline compatible with the oldest CPU model present, or keep newer/older "
                "generations in separate clusters."
            ),
            limitations=(
                "Compares raw SMBIOS CPU model strings across hosts in this assessment only; it "
                "has no visibility into vCenter cluster membership or EVC configuration, so it "
                "cannot tell you whether these specific hosts actually share a cluster, or "
                "whether EVC is already mitigating the mismatch."
            ),
        )
    ]


def _vswitch_mtu_mismatch(hosts: list[HostInfo]) -> list[Finding]:
    by_name: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for host in hosts:
        for switch in host.network_switches:
            if switch.mtu is not None:
                by_name[switch.name][switch.mtu].append(host.hostname)

    findings = []
    for name, by_mtu in sorted(by_name.items()):
        if len(by_mtu) < 2:
            continue
        detail = "; ".join(
            f"MTU {mtu} on {', '.join(sorted(names))}" for mtu, names in sorted(by_mtu.items())
        )
        findings.append(
            Finding(
                rule_id="fleet.vswitch_mtu_mismatch",
                title="Inconsistent MTU for the same vSwitch/DVS across hosts",
                severity=Severity.MEDIUM,
                summary=(
                    f"Switch '{name}' is configured with different MTU values across "
                    f"the hosts in this assessment: {detail}."
                ),
                evidence=[f"esxcfg-vswitch -l: {name} -- {detail}"],
                remediation=(
                    "Align the MTU for this switch across every host that defines it -- "
                    "for a distributed switch (DVS) this is normally meant to be one "
                    "cluster-wide setting -- or confirm the difference is intentional."
                ),
                limitations=(
                    "Compares switches by exact name match across this assessment's "
                    "hosts only; a standard vSwitch name that happens to be reused "
                    "per-host with an intentionally different MTU would also match, "
                    "and this has no visibility into actual vCenter cluster membership."
                ),
            )
        )
    return findings


# vCenter's own default "Datastore usage on disk" alarm: Warning at 75% used,
# Critical/Alert at 85% used (Broadcom KB 450627). Reused here rather than a
# made-up threshold, since it is the number most vSphere admins already
# recognise.
_WARNING_USED_FRACTION = 0.75
_CRITICAL_USED_FRACTION = 0.85
_GIB = 1024**3


def _distinct_datastores(hosts: list[HostInfo]) -> dict[str, tuple[str, int, int]]:
    """Every datastore across the fleet, deduplicated by UUID (falling back

    to name, matching ``datastore.py``'s own per-host dedup key), since a
    shared VMFS volume is typically mounted -- and independently
    reported -- by every host in the assessment; without this, the same
    real problem would otherwise raise one finding per host that mounts it.
    """
    seen: dict[str, tuple[str, int, int]] = {}
    for host in hosts:
        for ds in host.datastores:
            if not ds.capacity_bytes or ds.available_bytes is None:
                continue
            key = ds.uuid or ds.name
            seen.setdefault(key, (ds.name, ds.capacity_bytes, ds.available_bytes))
    return seen


def _datastore_usage_finding(
    name: str, capacity: int, available: int, rule_id: str, title: str,
    severity: Severity, threshold_label: str,
) -> Finding:
    used_pct = (1 - available / capacity) * 100
    return Finding(
        rule_id=rule_id,
        title=title,
        severity=severity,
        summary=(
            f"Datastore '{name}' is {used_pct:.1f}% full "
            f"({available / _GIB:.1f} GiB free of {capacity / _GIB:.1f} GiB total), past "
            f"vCenter's own default {threshold_label} usage-alarm threshold."
        ),
        evidence=[f"vmkfstools -P -v 10: {name} -- {used_pct:.1f}% used"],
        affected_object=name,
        remediation=(
            "Review what is consuming space on this datastore (snapshots, orphaned "
            "VMDKs, swap files) and either reclaim space or migrate some VMs to "
            "another datastore before it fills further."
        ),
        limitations=(
            "A point-in-time snapshot from this bundle's capture moment, read directly "
            "from each host's own VMFS volume data (vmkfstools -P -v 10); a shared "
            "datastore mounted by several hosts in this assessment is reported once "
            "here, deduplicated by UUID, not once per host. Thin-provisioned VMDKs and "
            "snapshot growth can consume space between capture and when this report "
            "is read."
        ),
    )


def _datastore_usage_critical(hosts: list[HostInfo]) -> list[Finding]:
    findings = []
    for name, capacity, available in sorted(_distinct_datastores(hosts).values()):
        if (1 - available / capacity) < _CRITICAL_USED_FRACTION:
            continue
        findings.append(
            _datastore_usage_finding(
                name, capacity, available, "fleet.datastore_usage_critical",
                "Datastore is critically low on free space", Severity.HIGH,
                "critical (85% used)",
            )
        )
    return findings


def _datastore_usage_warning(hosts: list[HostInfo]) -> list[Finding]:
    findings = []
    for name, capacity, available in sorted(_distinct_datastores(hosts).values()):
        used_fraction = 1 - available / capacity
        if used_fraction < _WARNING_USED_FRACTION or used_fraction >= _CRITICAL_USED_FRACTION:
            continue
        findings.append(
            _datastore_usage_finding(
                name, capacity, available, "fleet.datastore_usage_warning",
                "Datastore is running low on free space", Severity.MEDIUM,
                "warning (75% used)",
            )
        )
    return findings


RULES: list[FleetRule] = [
    FleetRule(
        rule_id="fleet.cpu_model_mismatch",
        title="Multiple CPU models detected across assessed hosts",
        default_severity=Severity.MEDIUM,
        evidence_required=("cpu_model",),
        limitations=(
            "Compares CPU model strings only; has no visibility into actual vCenter cluster "
            "membership or EVC configuration."
        ),
        evaluate=_cpu_model_mismatch,
    ),
    FleetRule(
        rule_id="fleet.vswitch_mtu_mismatch",
        title="Inconsistent MTU for the same vSwitch/DVS across hosts",
        default_severity=Severity.MEDIUM,
        evidence_required=("network_switches[].mtu",),
        limitations=(
            "Compares switches by exact name match only; has no visibility into actual "
            "vCenter cluster membership."
        ),
        evaluate=_vswitch_mtu_mismatch,
    ),
    FleetRule(
        rule_id="fleet.datastore_usage_warning",
        title="Datastore is running low on free space",
        default_severity=Severity.MEDIUM,
        evidence_required=("datastores[].capacity_bytes", "datastores[].available_bytes"),
        limitations=(
            "Point-in-time snapshot at capture only, from each host's own VMFS volume "
            "data; deduplicated by UUID across hosts that share a datastore."
        ),
        evaluate=_datastore_usage_warning,
    ),
    FleetRule(
        rule_id="fleet.datastore_usage_critical",
        title="Datastore is critically low on free space",
        default_severity=Severity.HIGH,
        evidence_required=("datastores[].capacity_bytes", "datastores[].available_bytes"),
        limitations=(
            "Point-in-time snapshot at capture only, from each host's own VMFS volume "
            "data; deduplicated by UUID across hosts that share a datastore."
        ),
        evaluate=_datastore_usage_critical,
    ),
]
