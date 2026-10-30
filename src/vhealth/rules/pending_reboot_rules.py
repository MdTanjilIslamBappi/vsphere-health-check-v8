"""Staged-but-not-rebooted image profile health check.

A host that applied an ESXi update (new VIBs staged into a pending
image profile) but was never rebooted is still running its old
software the whole time -- patches that look "installed" from the
active profile alone are not actually in effect. ``esxcli software
profile get --rebooting-image`` reports the real pending profile name
when one exists, or the literal ``No pending image profile available.``
when it does not.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _pending_reboot_image(host: HostInfo) -> list[Finding]:
    if not host.pending_reboot_data_available or host.pending_reboot_image_name is None:
        return []

    return [
        Finding(
            rule_id="hardware.pending_reboot_image",
            title="Host has an image profile staged but not yet applied by a reboot",
            severity=Severity.MEDIUM,
            summary=(
                f"{host.hostname} has a pending image profile "
                f"('{host.pending_reboot_image_name}') staged but not yet active -- "
                "this host has not rebooted since its last update was applied."
            ),
            evidence=[
                "esxcli software profile get --rebooting-image: "
                f"{host.pending_reboot_image_name}"
            ],
            affected_host=host.hostname,
            remediation=(
                "Schedule a maintenance-mode reboot of this host to bring the pending "
                "image profile into effect; until then, any VIB/patch believed already "
                "installed is not actually running."
            ),
            limitations=(
                "Reports a point-in-time snapshot from the bundle's capture moment "
                "only; cannot tell how long the reboot has been pending or why it was "
                "deferred."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.pending_reboot_image",
        title="Host has an image profile staged but not yet applied by a reboot",
        default_severity=Severity.MEDIUM,
        evidence_required=("pending_reboot_image_name",),
        limitations="Point-in-time snapshot at capture only.",
        evaluate=_pending_reboot_image,
    ),
]
