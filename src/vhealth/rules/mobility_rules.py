"""ESXi's own built-in migration-network (vMotion/Provisioning) health check.

Unlike every other rule in this catalogue, the verdict here comes
directly from ESXi's own ``vmware.mobility.mobility_health_checks``
module (see ``parsers/mobility.py``), not from pattern-matching raw
state. A ``status`` of ``"ERROR"`` is that tool's own conclusion that
the named network service (vMotion, Provisioning, ...) is not
currently healthy on this host.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

_ERROR_STATUS = "ERROR"


def _mobility_health_check_error(host: HostInfo) -> list[Finding]:
    findings = []
    for check in host.mobility_checks:
        if check.status != _ERROR_STATUS:
            continue
        evidence = [
            f"mobility_network_health_check: {check.net_service} network health "
            f"check status = {check.status}"
        ]
        if check.expected_destinations and check.tested_destinations < check.expected_destinations:
            evidence.append(
                f"Only {check.tested_destinations} of {check.expected_destinations} "
                f"expected {check.net_service} peer destination(s) were actually "
                "tested for connectivity"
            )
        evidence.extend(f"error: {e}" for e in check.errors)
        findings.append(
            Finding(
                rule_id="network.mobility_health_check_error",
                title=f"{check.net_service} network health check reported ERROR",
                severity=Severity.HIGH,
                summary=(
                    f"{host.hostname}: ESXi's own {check.net_service.lower()} "
                    "migration-network health check reported an overall ERROR "
                    "status, not something vhealth inferred."
                ),
                evidence=evidence,
                affected_host=host.hostname,
                affected_object=check.net_service,
                remediation=(
                    "Review this host's VMkernel adapter tagging for the affected "
                    "traffic type (vMotion/Provisioning -- 'esxcli network ip "
                    "interface tag get'), and confirm network connectivity to the "
                    "other hosts this service needs to reach."
                ),
                limitations=(
                    "This is ESXi's own built-in migration-network health check "
                    "tool, run once at capture time; a transient condition (a peer "
                    "host rebooting at that moment, etc.) could also cause this. "
                    "The tool fails to run at all on some ESXi builds/configurations "
                    "(observed as a Python traceback in the bundle instead of JSON), "
                    "in which case this host is not assessed by this rule at all."
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="network.mobility_health_check_error",
        title="Migration network health check reported ERROR",
        default_severity=Severity.HIGH,
        evidence_required=("mobility_checks[].status",),
        limitations=(
            "Point-in-time snapshot at capture only, from ESXi's own health-check "
            "tool; that tool itself fails to run at all on some hosts."
        ),
        evaluate=_mobility_health_check_error,
    ),
]
