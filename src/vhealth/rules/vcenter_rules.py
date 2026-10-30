"""Rules that inspect the parsed vCenter Server appliance bundle.

These rules run once per assessment on the (optional) ``VCenterInfo``
record -- not per host -- so they live outside the per-host ``Rule``/
``FleetRule`` types but follow the same evidence/limitations contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vhealth.models.findings import Finding, Severity
from vhealth.models.vcenter import VCenterInfo

# Services whose absence means the management plane is degraded or
# unavailable. Anything else that shows as stopped is judged optional;
# many vc-support captures legitimately show optional/feature-dependent
# services (vcha, autodeploy, imagebuilder, ...) as stopped.
_CORE_VCENTER_SERVICES = {
    "vpxd",
    "vmware-vpxd",
    "vmware-vpostgres",
    "vmware-rhttpproxy",
    "lookupsvc",
    "vmdird",
    "vmcad",
    "vmware-stsd",
    "vmware-content-library",
    "vmware-vmon",
    "vmware-vpxd-svcs",
}

_DISK_USAGE_MEDIUM_PERCENT = 90
_DISK_USAGE_HIGH_PERCENT = 95


@dataclass(frozen=True)
class VCenterRule:
    rule_id: str
    title: str
    default_severity: Severity
    evidence_required: tuple[str, ...]
    limitations: str
    evaluate: Callable[[VCenterInfo], list[Finding]]

    def run(self, vcenter: VCenterInfo) -> list[Finding]:
        try:
            return self.evaluate(vcenter)
        except Exception as exc:  # noqa: BLE001
            return [
                Finding(
                    rule_id=self.rule_id,
                    title=f"{self.title} (rule error)",
                    severity=Severity.INFO,
                    summary=f"Rule raised an unexpected error and was skipped: {exc}",
                    affected_host=vcenter.hostname,
                    limitations=self.limitations,
                )
            ]


def _evidence_line(vcenter: VCenterInfo, suffix: str) -> str:
    return f"{vcenter.hostname}: {suffix}"


def _stopped_service_findings(vcenter: VCenterInfo) -> list[Finding]:
    stopped = [s for s in vcenter.services_stopped if s in _CORE_VCENTER_SERVICES]
    if not stopped:
        return []
    return [
        Finding(
            rule_id="vcenter.core_service_stopped",
            title="Core vCenter Server service is stopped",
            severity=Severity.HIGH,
            summary=(
                f"{len(stopped)} core vCenter service(s) were stopped at capture time on "
                f"{vcenter.hostname}: {', '.join(sorted(stopped))}."
            ),
            evidence=[
                _evidence_line(vcenter, f"service-control: {s} stopped") for s in sorted(stopped)
            ],
            affected_host=vcenter.hostname,
            remediation=(
                "Log in to the VCSA shell and check the service with "
                "'service-control --status --all' and the var/log/vmware/<service>/ logs; "
                "restart via 'service-control --start <service>' and investigate why it "
                "stopped."
            ),
            limitations=(
                "Determines core-service state only from the capture-time snapshot in "
                "the bundle; a stopped service can be expected during a scheduled "
                "maintenance window, so confirm against change records."
            ),
        )
    ]


def _optional_stopped_service_findings(vcenter: VCenterInfo) -> list[Finding]:
    stopped = [s for s in vcenter.services_stopped if s not in _CORE_VCENTER_SERVICES]
    if not stopped:
        return []
    return [
        Finding(
            rule_id="vcenter.optional_service_stopped",
            title="Non-core vCenter service(s) reported stopped",
            severity=Severity.INFO,
            summary=(
                f"{len(stopped)} non-core service(s) were stopped at capture time on "
                f"{vcenter.hostname}: {', '.join(sorted(stopped))}. Many of these are "
                "optional and only run when their feature is enabled (for example "
                "vCHA, Auto Deploy, Image Builder)."
            ),
            evidence=[
                _evidence_line(vcenter, f"service-control: {s} stopped") for s in sorted(stopped)
            ],
            affected_host=vcenter.hostname,
            remediation=(
                "Confirm each stopped service matches the features actually used on "
                "this vCenter; start and investigate any service that should be "
                "running for features you rely on."
            ),
            limitations=(
                "Snapshot at capture time only; stopped optional services are often "
                "intentional (feature not deployed), so this is informational."
            ),
        )
    ]


def _disk_usage_findings(vcenter: VCenterInfo) -> list[Finding]:
    findings: list[Finding] = []
    # One finding per appliance mount that crosses a threshold -- /storage/*
    # partitions are separate LVM volumes and each must be treated on its own.
    for disk in vcenter.appliance_disks:
        percent = disk.percent_used
        if percent is None:
            continue
        if percent >= _DISK_USAGE_HIGH_PERCENT:
            severity = Severity.HIGH
        elif percent >= _DISK_USAGE_MEDIUM_PERCENT:
            severity = Severity.MEDIUM
        else:
            continue
        findings.append(
            Finding(
                rule_id="vcenter.appliance_disk_usage",
                title="vCenter appliance filesystem usage is high",
                severity=severity,
                summary=(
                    f"{disk.mount} on {vcenter.hostname} is {percent}% used "
                    f"({_human(disk.used_bytes)} of {_human(disk.size_bytes)})."
                ),
                evidence=[
                    _evidence_line(
                        vcenter,
                        f"df: {disk.mount} {percent}% used "
                        f"({_human(disk.used_bytes)} / {_human(disk.size_bytes)})",
                    )
                ],
                affected_host=vcenter.hostname,
                affected_object=disk.mount,
                remediation=(
                    f"Free space on {disk.mount}: for /storage/archive, aged event/task "
                    "data can be reduced by lowering vCenter's event retention, and "
                    "log partitions by adjusting syslog/DMESG rotation; otherwise extend "
                    "the volume following VMware's VCSA disk-sizing guidance before it "
                    "reaches 100%."
                ),
                limitations=(
                    "Usage snapshot at capture time only; a single reading cannot "
                    "distinguish a slow trend from a transient spike. Thresholds: "
                    f"{_DISK_USAGE_MEDIUM_PERCENT}%=medium, {_DISK_USAGE_HIGH_PERCENT}%=high."
                ),
            )
        )
    return findings


def _human(size: int | None) -> str:
    if size is None:
        return "unknown"
    size = float(size)
    for unit in ("GiB", "MiB", "KiB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


ALL_VCENTER_RULES: list[VCenterRule] = [
    VCenterRule(
        rule_id="vcenter.core_service_stopped",
        title="Core vCenter Server service is stopped",
        default_severity=Severity.HIGH,
        evidence_required=("services_stopped",),
        limitations="Capture-time snapshot only; confirm against change records.",
        evaluate=_stopped_service_findings,
    ),
    VCenterRule(
        rule_id="vcenter.optional_service_stopped",
        title="Non-core vCenter service(s) reported stopped",
        default_severity=Severity.INFO,
        evidence_required=("services_stopped",),
        limitations=(
            "Snapshot at capture time only; stopped optional services are often intentional."
        ),
        evaluate=_optional_stopped_service_findings,
    ),
    VCenterRule(
        rule_id="vcenter.appliance_disk_usage",
        title="vCenter appliance filesystem usage is high",
        default_severity=Severity.MEDIUM,
        evidence_required=("appliance_disks",),
        limitations=(
            "Single capture-time reading; thresholds 90%=medium, 95%=high."
        ),
        evaluate=_disk_usage_findings,
    ),
]


def evaluate_all_vcenter(
    vcenter: VCenterInfo | None, disabled_rules: tuple[str, ...] = ()
) -> list[Finding]:
    if vcenter is None:
        return []
    enabled_rules = [r for r in ALL_VCENTER_RULES if r.rule_id not in disabled_rules]
    findings: list[Finding] = []
    for rule in enabled_rules:
        findings.extend(rule.run(vcenter))
    return findings
