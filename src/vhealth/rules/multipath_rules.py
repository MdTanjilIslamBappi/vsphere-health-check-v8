"""Storage multipath path-state health checks.

``esxcli storage nmp path list`` reports every physical path ESXi
currently knows about for every storage device, each with a
``Group State`` of ``active``/``active unoptimized`` (ALUA, both
healthy) or ``dead``. This is a direct point-in-time snapshot, unlike
the vmkwarning-log-derived ``storage.path_dead_detected``, which only
sees a dead-path *event* if one was logged during the retained log
window -- a path that has been dead since before the oldest retained
rotation, with no fresh event to log, would be invisible to that rule
but is caught here.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _multipath_all_paths_dead(host: HostInfo) -> list[Finding]:
    findings = []
    for device in host.multipath_devices:
        if device.total_paths == 0 or device.dead_paths != device.total_paths:
            continue
        findings.append(
            Finding(
                rule_id="storage.multipath_all_paths_dead",
                title="All multipathing paths to a storage device are dead",
                severity=Severity.CRITICAL,
                summary=(
                    f"{host.hostname}: all {device.total_paths} path(s) to device "
                    f"{device.device} ({device.display_name or 'unknown model'}) report "
                    "'Group State: dead'; this device is currently inaccessible via "
                    "multipathing."
                ),
                evidence=[
                    f"localcli storage nmp path list: {device.device} -- "
                    f"{device.dead_paths} of {device.total_paths} path(s) Group State = dead"
                ],
                affected_host=host.hostname,
                affected_object=device.device,
                remediation=(
                    "Check SAN/array-side presentation, zoning, and HBA link state for "
                    "this device immediately; any VM/datastore backed by it is likely "
                    "already affected or about to be."
                ),
                limitations=(
                    "A point-in-time snapshot from the bundle's capture moment; a path "
                    "that recovered after capture is not reflected. Does not confirm "
                    "whether any datastore/VM is actually backed by this specific device."
                ),
            )
        )
    return findings


def _multipath_reduced_redundancy(host: HostInfo) -> list[Finding]:
    findings = []
    for device in host.multipath_devices:
        if device.dead_paths == 0 or device.dead_paths >= device.total_paths:
            continue
        findings.append(
            Finding(
                rule_id="storage.multipath_reduced_redundancy",
                title="Storage device has one or more dead multipathing paths",
                severity=Severity.HIGH,
                summary=(
                    f"{host.hostname}: {device.dead_paths} of {device.total_paths} "
                    f"path(s) to device {device.device} "
                    f"({device.display_name or 'unknown model'}) report "
                    "'Group State: dead'; path redundancy to this device is reduced."
                ),
                evidence=[
                    f"localcli storage nmp path list: {device.device} -- "
                    f"{device.dead_paths} of {device.total_paths} path(s) Group State = dead"
                ],
                affected_host=host.hostname,
                affected_object=device.device,
                remediation=(
                    "Check SAN/array-side presentation, zoning, and HBA link state for "
                    "the dead path(s); the device is still reachable but has lost "
                    "redundancy, raising the risk of a future all-paths-down condition "
                    "if the remaining path(s) also fail."
                ),
                limitations=(
                    "A point-in-time snapshot from the bundle's capture moment; a path "
                    "that recovered after capture is not reflected."
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="storage.multipath_all_paths_dead",
        title="All multipathing paths to a storage device are dead",
        default_severity=Severity.CRITICAL,
        evidence_required=("multipath_devices[].dead_paths", "multipath_devices[].total_paths"),
        limitations=(
            "Point-in-time snapshot at capture only; does not confirm which "
            "datastore/VM (if any) is backed by the affected device."
        ),
        evaluate=_multipath_all_paths_dead,
    ),
    Rule(
        rule_id="storage.multipath_reduced_redundancy",
        title="Storage device has one or more dead multipathing paths",
        default_severity=Severity.HIGH,
        evidence_required=("multipath_devices[].dead_paths", "multipath_devices[].total_paths"),
        limitations="Point-in-time snapshot at capture only.",
        evaluate=_multipath_reduced_redundancy,
    ),
]
