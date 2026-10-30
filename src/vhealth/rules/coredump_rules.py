"""Kernel-coredump target configuration health check.

A host with no coredump target configured can't write a kernel crash
dump when it PSODs -- the single most useful artifact VMware GSS asks
for to root-cause a host crash. Modern ESXi (6.5+) uses a file-based
coredump target (``esxcli system coredump file list``); the older
partition-based config is legacy and reports blank on these hosts, so
``coredump.py`` reads the file-based table instead.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _coredump_not_configured(host: HostInfo) -> list[Finding]:
    if not host.coredump_data_available or host.coredump_configured is not False:
        return []

    return [
        Finding(
            rule_id="hardware.coredump_not_configured",
            title="No active kernel-coredump target configured",
            severity=Severity.MEDIUM,
            summary=(
                f"{host.hostname} has no coredump file marked both Active and "
                "Configured; if this host PSODs, there is nowhere for ESXi to write "
                "the kernel crash dump needed to root-cause it."
            ),
            evidence=[
                "localcli system coredump file list: no Active=true/Configured=true row"
            ],
            affected_host=host.hostname,
            remediation=(
                "Configure a coredump target on a local VMFS datastore ('esxcli system "
                "coredump file add', then '--enable true'), or review the existing "
                "target with 'esxcli system coredump file list'."
            ),
            limitations=(
                "Reports a point-in-time snapshot from the bundle's capture moment "
                "only. The firing (not-configured) case is implemented from "
                "documented esxcli behaviour; every real bundle seen so far has at "
                "least one Active=true/Configured=true row, so this condition has "
                "not yet been observed firing against real-world data."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.coredump_not_configured",
        title="No active kernel-coredump target configured",
        default_severity=Severity.MEDIUM,
        evidence_required=("coredump_configured",),
        limitations=(
            "Point-in-time snapshot at capture only; implemented from documented "
            "esxcli behaviour but not yet observed firing against real-world data."
        ),
        evaluate=_coredump_not_configured,
    ),
]
