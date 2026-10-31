"""ESXi's own built-in core-service-running check (healthd's

vmw.coreServicesStatus). ``core_service_pids`` maps each tracked service
name to its PID, where ``0`` means "not running" -- healthd's own
verdict, not something vhealth infers.

``vsanmgmtd`` is handled specially: on the real EAMSC2 bundle it
legitimately reports PID ``0`` on every host where
``vsan_status.py``'s ``vSAN_cluster_enabled`` is ``False`` -- vSAN is
simply disabled there, which is not a failure. This rule only treats
``vsanmgmtd == 0`` as a problem when ``vsan_cluster_enabled`` is
actually ``True`` for that host; when it is ``False`` or unknown,
``vsanmgmtd`` is silently excluded from this check (never flagged), and
the report's "Core Services Status" component row says so explicitly
(see ``reporting/summary.py``) rather than leaving a reader to wonder
why vsanmgmtd was not considered.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

# Services expected to be running on every host regardless of vSAN state.
_ALWAYS_EXPECTED_SERVICES = ("healthd", "hostd", "hostd-probe", "vpxa")
_VSAN_SERVICE = "vsanmgmtd"


def _core_service_not_running(host: HostInfo) -> list[Finding]:
    if not host.core_services_data_available:
        return []

    dead = [
        name for name in _ALWAYS_EXPECTED_SERVICES if host.core_service_pids.get(name) == 0
    ]
    if host.vsan_cluster_enabled and host.core_service_pids.get(_VSAN_SERVICE) == 0:
        dead.append(_VSAN_SERVICE)
    if not dead:
        return []

    evidence = [f"vmw.coreServicesStatus: {name}=0 (not running)" for name in dead]

    return [
        Finding(
            rule_id="hardware.core_service_not_running",
            title="A core ESXi management service is not running",
            severity=Severity.CRITICAL,
            summary=(
                f"{host.hostname}: ESXi's own healthd check reports the following core "
                f"service(s) not running: {', '.join(dead)}."
            ),
            evidence=evidence,
            affected_host=host.hostname,
            affected_object=", ".join(dead),
            remediation=(
                "Check 'services.sh status' / 'ps | grep <service>' on this host and "
                "restart the affected service via the vSphere Client or "
                "'/etc/init.d/<service> restart'; investigate hostd/vpxa logs "
                "(/var/log/hostd.log, /var/log/vpxa.log) for the cause if it keeps "
                "stopping."
            ),
            limitations=(
                "Point-in-time snapshot from ESXi's own healthd check, selecting "
                "whichever rotated snapshot has the most recent timestamp in the bundle. "
                "'vsanmgmtd' is only ever flagged when this host's vmw.vSANStatus check "
                "reports vSAN enabled -- it legitimately shows PID 0 on a host with vSAN "
                "disabled, which this rule does not treat as a failure."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.core_service_not_running",
        title="A core ESXi management service is not running",
        default_severity=Severity.CRITICAL,
        evidence_required=("core_service_pids",),
        limitations="Point-in-time snapshot at capture only, from ESXi's own healthd check.",
        evaluate=_core_service_not_running,
    ),
]
