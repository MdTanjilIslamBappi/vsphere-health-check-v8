"""ESXi's own built-in memory-health check (healthd's vmw.memoryHealth).

Unlike most rules in this catalogue, the verdict here comes directly
from ESXi's own ``healthd`` self-check (see ``parsers/memory_health.py``),
not from pattern-matching raw state. Two independent sub-states are
each evaluated by their own rule: ``hardware_state`` is healthd's own
read of physical/ECC memory health, and ``reservation_state`` is its
read of the host's memory-reservation admission-control health -- a
host can have failing memory hardware while still meeting its
reservations, or vice versa.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

_HEALTHY_STATE = "Green"


def _memory_hardware_health_degraded(host: HostInfo) -> list[Finding]:
    if not host.memory_health_data_available or host.memory_hardware_state is None:
        return []
    if host.memory_hardware_state == _HEALTHY_STATE:
        return []

    evidence = [f"vmw.memoryHealth: hardware_state = {host.memory_hardware_state}"]
    if host.memory_corrected_errors_since_boot is not None:
        evidence.append(
            f"total_corrected_errors_since_boot = {host.memory_corrected_errors_since_boot}"
        )
    if host.memory_uncorrected_errors_since_boot is not None:
        evidence.append(
            f"total_uncorrected_errors_since_boot = {host.memory_uncorrected_errors_since_boot}"
        )

    return [
        Finding(
            rule_id="hardware.memory_hardware_health_degraded",
            title="ESXi reports degraded physical memory (ECC) health",
            severity=Severity.CRITICAL,
            summary=(
                f"{host.hostname}: ESXi's own healthd memory-hardware check reports "
                f"'{host.memory_hardware_state}', not the healthy 'Green' state."
            ),
            evidence=evidence,
            affected_host=host.hostname,
            remediation=(
                "Check the host's IPMI SEL and hardware management console for ECC/DIMM "
                "errors, and schedule a physical memory inspection/reseat or replacement "
                "via the vendor's diagnostics if this persists."
            ),
            limitations=(
                "This is ESXi's own built-in healthd memory-health check, sampled every "
                "few minutes; this reports whichever rotated snapshot has the most recent "
                "timestamp in the bundle, a point-in-time result at that moment only."
            ),
        )
    ]


def _memory_reservation_health_degraded(host: HostInfo) -> list[Finding]:
    if not host.memory_health_data_available or host.memory_reservation_state is None:
        return []
    if host.memory_reservation_state == _HEALTHY_STATE:
        return []

    return [
        Finding(
            rule_id="hardware.memory_reservation_health_degraded",
            title="ESXi reports degraded memory-reservation health",
            severity=Severity.MEDIUM,
            summary=(
                f"{host.hostname}: ESXi's own healthd memory-reservation check reports "
                f"'{host.memory_reservation_state}', not the healthy 'Green' state -- the "
                "host may be unable to meet configured memory reservations/admission control."
            ),
            evidence=[f"vmw.memoryHealth: reservation_state = {host.memory_reservation_state}"],
            affected_host=host.hostname,
            remediation=(
                "Review this host's current memory consumption and reservations (e.g. "
                "'esxcli system settings advanced list' / vSphere Client Performance tab) "
                "for overcommitment, and consider reducing reserved memory or adding capacity."
            ),
            limitations=(
                "This is ESXi's own built-in healthd memory-health check, sampled every "
                "few minutes; this reports whichever rotated snapshot has the most recent "
                "timestamp in the bundle, a point-in-time result at that moment only."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.memory_hardware_health_degraded",
        title="ESXi reports degraded physical memory (ECC) health",
        default_severity=Severity.CRITICAL,
        evidence_required=("memory_hardware_state",),
        limitations=(
            "Point-in-time snapshot at capture only, from ESXi's own healthd check."
        ),
        evaluate=_memory_hardware_health_degraded,
    ),
    Rule(
        rule_id="hardware.memory_reservation_health_degraded",
        title="ESXi reports degraded memory-reservation health",
        default_severity=Severity.MEDIUM,
        evidence_required=("memory_reservation_state",),
        limitations=(
            "Point-in-time snapshot at capture only, from ESXi's own healthd check."
        ),
        evaluate=_memory_reservation_health_degraded,
    ),
]
