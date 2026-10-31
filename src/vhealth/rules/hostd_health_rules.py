"""ESXi's own built-in hostd-responsiveness check (healthd's

hostd-health). Distinct from ``core_services_rules.py``'s PID-based
check: a hung hostd can hold a live PID while failing to actually
respond to probes, which this check catches and the PID-based one
cannot.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _hostd_unresponsive(host: HostInfo) -> list[Finding]:
    if not host.hostd_health_data_available or host.hostd_responsive is None:
        return []
    if host.hostd_responsive:
        return []

    return [
        Finding(
            rule_id="hardware.hostd_unresponsive",
            title="hostd is not responding to ESXi's own health probe",
            severity=Severity.CRITICAL,
            summary=(
                f"{host.hostname}: ESXi's own hostd-health healthd check reports hostd "
                "is not in the 'Responsive' state, even though its process may still be "
                "running."
            ),
            evidence=["hostd-health: hostd.state != 'Responsive'"],
            affected_host=host.hostname,
            remediation=(
                "An unresponsive hostd typically means the management agent is hung "
                "rather than crashed; restart it via "
                "'/etc/init.d/hostd restart' (direct host console/SSH, since the "
                "vSphere Client itself may be unreachable through a hung hostd), and "
                "check /var/log/hostd.log for the cause."
            ),
            limitations=(
                "Point-in-time snapshot from ESXi's own healthd check, selecting "
                "whichever rotated snapshot has the most recent timestamp in the bundle."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.hostd_unresponsive",
        title="hostd is not responding to ESXi's own health probe",
        default_severity=Severity.CRITICAL,
        evidence_required=("hostd_responsive",),
        limitations="Point-in-time snapshot at capture only, from ESXi's own healthd check.",
        evaluate=_hostd_unresponsive,
    ),
]
