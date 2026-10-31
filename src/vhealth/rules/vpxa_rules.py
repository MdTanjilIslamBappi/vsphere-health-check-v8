"""ESXi's own built-in vpxa<->hostd<->vCenter connectivity check (healthd's

vmw.vpxaStatus). Only evaluated when the host reports itself as
``managed_by_VC`` -- a standalone host or one legitimately not under
vCenter management is expected to show ``connected_to_hostd``/
``responsive`` as not applicable, which is not a problem.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

_HEALTHY_CONFIG_STATUS = "green"


def _vpxa_connectivity_degraded(host: HostInfo) -> list[Finding]:
    if not host.vpxa_status_data_available or not host.vpxa_managed_by_vc:
        return []

    problems = []
    if host.vpxa_responsive is False:
        problems.append("responsive=false")
    if host.vpxa_connected_to_hostd is False:
        problems.append("connected_to_hostd=false")
    if host.vpxa_config_status is not None and host.vpxa_config_status != _HEALTHY_CONFIG_STATUS:
        problems.append(f"config_status={host.vpxa_config_status}")
    if not problems:
        return []

    return [
        Finding(
            rule_id="network.vpxa_connectivity_degraded",
            title="vpxa reports a degraded connection to vCenter",
            severity=Severity.HIGH,
            summary=(
                f"{host.hostname}: ESXi's own vmw.vpxaStatus healthd check reports this "
                f"vCenter-managed host's vpxa connection is degraded ({', '.join(problems)})."
            ),
            evidence=[f"vmw.vpxaStatus: {p}" for p in problems],
            affected_host=host.hostname,
            remediation=(
                "Check vpxa's own log (/var/log/vpxa.log) for the cause, confirm network "
                "connectivity between this host and the vCenter Server, and restart vpxa "
                "via '/etc/init.d/vpxa restart' if it does not self-recover; vCenter may "
                "show this host as connected while this host's own agent disagrees."
            ),
            limitations=(
                "Point-in-time snapshot from ESXi's own healthd check, selecting "
                "whichever rotated snapshot has the most recent timestamp in the bundle; "
                "only evaluated when the host reports managed_by_VC=true."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="network.vpxa_connectivity_degraded",
        title="vpxa reports a degraded connection to vCenter",
        default_severity=Severity.HIGH,
        evidence_required=("vpxa_responsive", "vpxa_connected_to_hostd", "vpxa_config_status"),
        limitations="Point-in-time snapshot at capture only, from ESXi's own healthd check.",
        evaluate=_vpxa_connectivity_degraded,
    ),
]
