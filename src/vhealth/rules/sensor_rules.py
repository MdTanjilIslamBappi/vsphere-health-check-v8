from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _asserted_sensor(host: HostInfo) -> list[Finding]:
    findings = []
    for sensor in host.sensors:
        if sensor.status != "asserted":
            continue
        findings.append(
            Finding(
                rule_id="hardware.ipmi_sensor_asserted",
                title="IPMI hardware sensor is in an asserted (alarm) state",
                severity=Severity.HIGH,
                summary=(
                    f"Sensor '{sensor.name}' ({sensor.sensor_type or 'unknown type'}) is "
                    "in an asserted state, indicating an active hardware alarm condition "
                    "(e.g. a failed power supply, fan, or voltage rail)."
                ),
                evidence=[f"IPMI SDR: {sensor.name} = {sensor.reading}"],
                affected_host=host.hostname,
                affected_object=sensor.name,
                remediation=(
                    "Check the physical server's hardware/BMC event log and out-of-band "
                    "management console; this is a server-hardware condition, not a "
                    "virtualization-layer one."
                ),
                limitations=(
                    "Interprets only the discrete 'State Asserted'/'State Deasserted' IPMI "
                    "encoding; threshold-crossing analog sensors are not evaluated in v1."
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.ipmi_sensor_asserted",
        title="IPMI hardware sensor is in an asserted (alarm) state",
        default_severity=Severity.HIGH,
        evidence_required=("sensors[].status",),
        limitations="Only discrete asserted/deasserted sensors are evaluated in v1.",
        evaluate=_asserted_sensor,
    ),
]
