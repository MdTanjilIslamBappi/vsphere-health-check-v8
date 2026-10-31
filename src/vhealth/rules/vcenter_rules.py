"""Rules that inspect the parsed vCenter Server appliance bundle.

These rules run once per assessment on the (optional) ``VCenterInfo``
record -- not per host -- so they live outside the per-host ``Rule``/
``FleetRule`` types but follow the same evidence/limitations contract.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

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

# Certificate-expiry urgency windows, counted from the bundle's own
# capture date (never wall-clock "now" -- this is an offline, point-in-
# time assessment, so "today" must mean the day the bundle was captured).
# These day counts are vhealth's own choice, not VMware-documented.
_CERT_HIGH_URGENCY_DAYS = 30
_CERT_MEDIUM_URGENCY_DAYS = 90

_CAPTURED_ON_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


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


def _certificate_expiring_findings(vcenter: VCenterInfo) -> list[Finding]:
    captured_date = _parse_captured_date(vcenter.captured_on)
    if captured_date is None:
        return []

    findings: list[Finding] = []
    for cert in vcenter.sts_certificates:
        not_after = _parse_iso_datetime(cert.not_after)
        if not_after is None:
            continue
        days_until = (not_after.date() - captured_date).days

        if days_until <= 0:
            severity = Severity.CRITICAL
            urgency = f"expired {-days_until} day(s) before this bundle was captured"
        elif days_until <= _CERT_HIGH_URGENCY_DAYS:
            severity = Severity.HIGH
            urgency = f"expires in {days_until} day(s)"
        elif days_until <= _CERT_MEDIUM_URGENCY_DAYS:
            severity = Severity.MEDIUM
            urgency = f"expires in {days_until} day(s)"
        else:
            continue

        subject = cert.subject_cn or f"serial {cert.serial_number}"
        findings.append(
            Finding(
                rule_id="vcenter.sts_certificate_expiring",
                title="SSO/STS certificate is expiring soon or has expired",
                severity=severity,
                summary=(
                    f"{vcenter.hostname}: SSO/STS certificate '{subject}' (issuer "
                    f"'{cert.issuer_cn or 'unknown'}') {urgency} (not_after={cert.not_after}), "
                    f"relative to this bundle's own capture date."
                ),
                evidence=[
                    _evidence_line(
                        vcenter,
                        f"sts-certificates.txt: {subject} (serial {cert.serial_number}, "
                        f"entries: {', '.join(cert.entry_names) or 'unknown'}) "
                        f"not_after={cert.not_after}",
                    )
                ],
                affected_host=vcenter.hostname,
                affected_object=subject,
                remediation=(
                    "Renew the SSO/STS signing certificate via "
                    "'/usr/lib/vmware-vmafd/bin/certool' or the vSphere Client's "
                    "Certificate Management workflow before it expires -- an expired "
                    "STS signing certificate breaks SSO login for the whole environment."
                ),
                limitations=(
                    "Covers only the vsphere.local SSO signing certificates stored in "
                    "vmdir (sts-certificates.txt); the VECS-managed Machine SSL "
                    "certificate, solution-user certificates, and other VECS stores are "
                    "not captured in a vc-support bundle and are not assessed here. "
                    "Urgency windows "
                    f"({_CERT_HIGH_URGENCY_DAYS}/{_CERT_MEDIUM_URGENCY_DAYS} days) are "
                    "vhealth's own choice, not VMware-documented. Measured from this "
                    "bundle's own capture date, not the date this report is generated."
                ),
            )
        )
    return findings


def _parse_captured_date(captured_on: str | None):
    if not captured_on:
        return None
    match = _CAPTURED_ON_DATE_RE.match(captured_on)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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
    VCenterRule(
        rule_id="vcenter.sts_certificate_expiring",
        title="SSO/STS certificate is expiring soon or has expired",
        default_severity=Severity.MEDIUM,
        evidence_required=("sts_certificates[].not_after",),
        limitations=(
            f"Covers only vsphere.local SSO signing certificates (sts-certificates.txt), "
            "not VECS-managed certificates; thresholds "
            f"{_CERT_HIGH_URGENCY_DAYS}/{_CERT_MEDIUM_URGENCY_DAYS} days are vhealth's own "
            "choice; measured from the bundle's own capture date."
        ),
        evaluate=_certificate_expiring_findings,
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
