"""Per-host network (vSwitch/DVS) health checks.

``esxcfg-vswitch -l`` reports every standard vSwitch and distributed
virtual switch (DVS) a host knows about, including its uplink NIC list.
A switch with exactly one physical uplink has no NIC/cable/upstream-
switch-port redundancy -- if that one uplink fails, everything on the
switch loses connectivity.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

# The BMC/iDRAC out-of-band management vSwitch uses a virtual USB NIC
# (vusb0) as its one and only "uplink" by design -- there is no physical
# redundancy to have here, so it is not a real single-point-of-failure
# the way a missing second vmnic on a production switch is.
_VIRTUAL_UPLINK_PREFIX = "vusb"


def _real_uplinks(uplinks: list[str]) -> list[str]:
    return [u for u in uplinks if not u.lower().startswith(_VIRTUAL_UPLINK_PREFIX)]


def _vswitch_single_uplink(host: HostInfo) -> list[Finding]:
    findings = []
    for switch in host.network_switches:
        real_uplinks = _real_uplinks(switch.uplinks)
        if len(real_uplinks) != 1:
            continue
        kind = "DVS" if switch.is_distributed else "vSwitch"
        findings.append(
            Finding(
                rule_id="network.vswitch_single_uplink",
                title="Network switch has only one uplink (no NIC redundancy)",
                severity=Severity.MEDIUM,
                summary=(
                    f"{host.hostname}: {kind} '{switch.name}' has only one uplink "
                    f"({real_uplinks[0]}); if that NIC, its cable, or its upstream "
                    "switch port fails, everything on this switch loses connectivity."
                ),
                evidence=[f"esxcfg-vswitch -l: {switch.name} Uplinks = {real_uplinks[0]}"],
                affected_host=host.hostname,
                affected_object=switch.name,
                remediation=(
                    "Add a second physical uplink from a different NIC (ideally on a "
                    "different physical card/PCIe bus) to this switch, or confirm this "
                    "is an intentionally non-redundant network."
                ),
                limitations=(
                    "Only counts the uplink NIC list this command reports; it has no "
                    "visibility into whether those NICs sit on independent physical "
                    "cards or share a single point of failure upstream (e.g. the same "
                    "top-of-rack switch)."
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="network.vswitch_single_uplink",
        title="Network switch has only one uplink (no NIC redundancy)",
        default_severity=Severity.MEDIUM,
        evidence_required=("network_switches[].uplinks",),
        limitations=(
            "Only counts the reported uplink NIC list; cannot see whether those NICs "
            "are actually independent upstream."
        ),
        evaluate=_vswitch_single_uplink,
    ),
]
