from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _smart_health_not_ok(host: HostInfo) -> list[Finding]:
    findings = []
    for device in host.storage_devices:
        health = device.smart_overall_health
        if health and health.strip().upper() != "OK":
            findings.append(
                Finding(
                    rule_id="storage.smart_health_not_ok",
                    title="Local disk reports non-OK SMART health",
                    severity=Severity.HIGH,
                    summary=(
                        f"Device {device.device} ({device.display_name or 'unknown model'}) "
                        f"reports SMART health status '{health}', not 'OK'."
                    ),
                    evidence=[f"smartinfo.txt: Health Status = {health}"],
                    affected_host=host.hostname,
                    affected_object=device.device,
                    remediation=(
                        "Schedule replacement of the affected disk; verify it is not the "
                        "last remaining redundant member of its RAID/VSAN disk group first."
                    ),
                    limitations=(
                        "Only disks whose driver exposes SMART to ESXi (typically local "
                        "SAS/SATA/NVMe) report this; SAN LUNs behind an FC/iSCSI HBA do not."
                    ),
                )
            )
    return findings


def _smart_reallocated_sectors(host: HostInfo) -> list[Finding]:
    findings = []
    for device in host.storage_devices:
        reallocated = device.smart_raw.get("Reallocated Sector Count")
        if reallocated and reallocated.isdigit() and int(reallocated) > 0:
            findings.append(
                Finding(
                    rule_id="storage.smart_reallocated_sectors",
                    title="Local disk has reallocated sectors",
                    severity=Severity.MEDIUM,
                    summary=(
                        f"Device {device.device} has a non-zero Reallocated Sector Count "
                        f"({reallocated}), a classic early indicator of media wear."
                    ),
                    evidence=[f"smartinfo.txt: Reallocated Sector Count = {reallocated}"],
                    affected_host=host.hostname,
                    affected_object=device.device,
                    remediation="Monitor trend; plan proactive replacement if the count grows.",
                    limitations="A small, stable count on an older drive is not urgent by itself.",
                )
            )
    return findings


def _unredundant_single_path_device(host: HostInfo) -> list[Finding]:
    findings = []
    for device in host.storage_devices:
        if device.is_local:
            continue
        if device.multipath_plugin and device.status and device.status.lower() != "on":
            datastore_name = host.datastore_for_naa(device.device)
            datastore_note = (
                f"the '{datastore_name}' datastore"
                if datastore_name
                else "datastores on this device"
            )
            findings.append(
                Finding(
                    rule_id="storage.device_not_on",
                    title="Storage device is not in the 'on' state",
                    severity=Severity.HIGH,
                    summary=(
                        f"Device {device.device} reports status '{device.status}' instead "
                        f"of 'on'; {datastore_note} may be inaccessible."
                    ),
                    evidence=[f"localcli storage-core device-list: Status = {device.status}"],
                    affected_host=host.hostname,
                    affected_object=device.device,
                    remediation="Check path state and array-side presentation for this device.",
                    limitations=(
                        "A device intentionally taken offline for maintenance also matches."
                    ),
                )
            )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="storage.smart_health_not_ok",
        title="Local disk reports non-OK SMART health",
        default_severity=Severity.HIGH,
        evidence_required=("storage_devices[].smart_overall_health",),
        limitations="Requires a driver that exposes SMART to ESXi; SAN LUNs are not covered.",
        evaluate=_smart_health_not_ok,
    ),
    Rule(
        rule_id="storage.smart_reallocated_sectors",
        title="Local disk has reallocated sectors",
        default_severity=Severity.MEDIUM,
        evidence_required=("storage_devices[].smart_raw",),
        limitations="A small, stable count on an older drive is not urgent by itself.",
        evaluate=_smart_reallocated_sectors,
    ),
    Rule(
        rule_id="storage.device_not_on",
        title="Storage device is not in the 'on' state",
        default_severity=Severity.HIGH,
        evidence_required=("storage_devices[].status",),
        limitations="Planned maintenance offline states are indistinguishable from failures.",
        evaluate=_unredundant_single_path_device,
    ),
]
