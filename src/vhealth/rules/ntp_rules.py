"""NTP time-synchronization health checks.

Clock drift across hosts breaks HA elections/heartbeats, vCenter
certificate and Kerberos-based auth, and makes cross-host log
correlation unreliable -- a standard item in any vSphere health check.
``esxcli system ntp get`` reports whether NTP is enabled *and*,
separately, whether the clock is actually synchronized right now; a host
can have NTP enabled with a server configured and still never actually
sync (e.g. an unreachable/misconfigured server), which is exactly the
gap this rule is for.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _ntp_not_synchronized(host: HostInfo) -> list[Finding]:
    if not host.ntp_data_available or host.ntp_time_synchronized is not False:
        return []

    servers = ", ".join(host.ntp_servers) if host.ntp_servers else "none configured"
    return [
        Finding(
            rule_id="hardware.ntp_not_synchronized",
            title="Host clock is not synchronized via NTP",
            severity=Severity.MEDIUM,
            summary=(
                f"{host.hostname} reports NTP 'Time Synchronized' = false (configured "
                f"server(s): {servers}); the host's clock is not actually synchronized, "
                "regardless of whether the NTP service is enabled."
            ),
            evidence=[
                "localcli system ntp get: Time Synchronized = false",
                f"localcli system ntp get: Servers = {servers}",
            ],
            affected_host=host.hostname,
            remediation=(
                "Verify the configured NTP server(s) are reachable from this host "
                "(firewall/routing/DNS), and confirm the NTP service is actually running "
                "('esxcli system ntp get'); clock drift affects HA heartbeats, vCenter "
                "certificate/Kerberos authentication, and cross-host log correlation."
            ),
            limitations=(
                "Reports a point-in-time snapshot from the bundle's capture moment only; "
                "a host that synced (or lost sync) before/after capture is not reflected."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.ntp_not_synchronized",
        title="Host clock is not synchronized via NTP",
        default_severity=Severity.MEDIUM,
        evidence_required=("ntp_time_synchronized", "ntp_servers"),
        limitations=(
            "Point-in-time snapshot at capture only; does not reflect sync state "
            "before/after capture."
        ),
        evaluate=_ntp_not_synchronized,
    ),
]
