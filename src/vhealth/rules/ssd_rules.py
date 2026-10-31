"""ESXi's own built-in per-SSD/NVMe-device operational check (healthd's

vmw.ssdStorageHealth). ``device_state_enum`` is healthd's own verdict,
not something vhealth infers; the only value observed in real data is
the known-good ``0``, so this rule flags any other value without
assuming a specific meaning for it.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

_HEALTHY_STATE_ENUM = 0


def _ssd_device_not_operational(host: HostInfo) -> list[Finding]:
    findings = []
    for device in host.ssd_devices:
        if device.device_state_enum in (None, _HEALTHY_STATE_ENUM):
            continue

        evidence = [
            f"vmw.ssdStorageHealth: device={device.device}, "
            f"device_state_enum={device.device_state_enum}"
        ]
        if device.device_state:
            evidence.append(f"device_state: {device.device_state}")
        if device.model or device.vendor:
            evidence.append(f"{device.vendor or ''} {device.model or ''}".strip())

        findings.append(
            Finding(
                rule_id="storage.ssd_device_not_operational",
                title="SSD/NVMe device reports a non-operational state",
                severity=Severity.HIGH,
                summary=(
                    f"{host.hostname}: ESXi's own healthd check reports SSD/NVMe device "
                    f"'{device.device}' in a non-operational state "
                    f"(device_state_enum={device.device_state_enum})."
                ),
                evidence=evidence,
                affected_host=host.hostname,
                affected_object=device.device,
                remediation=(
                    "Check this device's health via the vendor's own management tool "
                    "(e.g. a NVMe boot/cache device's controller utility) and the host's "
                    "IPMI SEL for related hardware events; plan a replacement if the "
                    "device is confirmed degraded."
                ),
                limitations=(
                    "Point-in-time snapshot from ESXi's own healthd check, selecting "
                    "whichever rotated snapshot has the most recent timestamp in the "
                    "bundle. Only the known-good device_state_enum value (0) has been "
                    "observed in real data; any other value is flagged without vhealth "
                    "assuming a specific severity meaning beyond 'not known-good'."
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="storage.ssd_device_not_operational",
        title="SSD/NVMe device reports a non-operational state",
        default_severity=Severity.HIGH,
        evidence_required=("ssd_devices[].device_state_enum",),
        limitations="Point-in-time snapshot at capture only, from ESXi's own healthd check.",
        evaluate=_ssd_device_not_operational,
    ),
]
