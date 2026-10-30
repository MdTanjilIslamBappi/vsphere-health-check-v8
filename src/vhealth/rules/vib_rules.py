"""Installed VIB acceptance-level health check.

ESXi enforces four acceptance levels on installed software:
``VMwareCertified``, ``VMwareAccepted``, ``PartnerSupported``, and
``CommunitySupported``. VMware GSS does not support issues on a host
running any ``CommunitySupported`` VIB -- a real operational/support
risk, not just a compliance nicety.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _community_supported_vib_installed(host: HostInfo) -> list[Finding]:
    if not host.vib_data_available or not host.community_supported_vibs:
        return []

    vib_names = sorted(host.community_supported_vibs)
    return [
        Finding(
            rule_id="hardware.community_supported_vib_installed",
            title="Host has a CommunitySupported (unsupported) VIB installed",
            severity=Severity.MEDIUM,
            summary=(
                f"{host.hostname} has {len(vib_names)} VIB(s) at the "
                f"'CommunitySupported' acceptance level: {', '.join(vib_names)}. "
                "VMware GSS does not provide support for issues these drivers or "
                "modules could be involved in."
            ),
            evidence=[
                f"localcli software vib list: {name} Acceptance Level = CommunitySupported"
                for name in vib_names
            ],
            affected_host=host.hostname,
            remediation=(
                "Replace the listed VIB(s) with a VMwareCertified/VMwareAccepted/"
                "PartnerSupported equivalent where one exists, or confirm with VMware/"
                "the vendor that this VIB is an accepted exception for this "
                "environment ('esxcli software vib list' to re-verify after any "
                "change)."
            ),
            limitations=(
                "Only reports the acceptance level ESXi itself records; it has no "
                "visibility into whether VMware GSS has separately approved an "
                "exception for this specific VIB in this environment."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.community_supported_vib_installed",
        title="Host has a CommunitySupported (unsupported) VIB installed",
        default_severity=Severity.MEDIUM,
        evidence_required=("community_supported_vibs",),
        limitations=(
            "Only reports the acceptance level ESXi itself records; cannot see any "
            "separately-granted GSS exception for a specific VIB."
        ),
        evaluate=_community_supported_vib_installed,
    ),
]
