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
]
