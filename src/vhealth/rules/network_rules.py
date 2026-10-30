"""Per-host network (vSwitch/DVS) health checks.

``esxcfg-vswitch -l`` reports every standard vSwitch and distributed
virtual switch (DVS) a host knows about, including its uplink NIC list.
A switch with exactly one physical uplink has no NIC/cable/upstream-
switch-port redundancy -- if that one uplink fails, everything on the
switch loses connectivity.

``_vswitch_uplink_link_down``/``_vswitch_all_uplinks_down`` go one step
further: ``esxcfg-vswitch -l`` only reports which NICs are *configured*
as uplinks, not whether they actually have a physical link right now.
Cross-referencing against ``nicinfo.sh`` (``host.nic_link_up``) catches
a switch that lists two uplinks for redundancy, but where one of them
has no cable/no link -- already-reduced redundancy that looks perfectly
healthy from ``esxcfg-vswitch -l`` alone.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo, NetworkSwitch
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


def _down_real_uplinks(host: HostInfo, switch: NetworkSwitch) -> tuple[list[str], list[str]]:
    """Real (non-virtual) uplinks for a switch, and which of them have no

    physical link. Only meaningful for a switch with 2+ real uplinks --
    0 or 1 is already ``network.vswitch_single_uplink``'s territory.
    """
    real_uplinks = _real_uplinks(switch.uplinks)
    if len(real_uplinks) < 2:
        return [], []
    down = [u for u in real_uplinks if host.nic_link_up(u) is False]
    return real_uplinks, down


def _vswitch_uplink_link_down(host: HostInfo) -> list[Finding]:
    findings = []
    for switch in host.network_switches:
        real_uplinks, down = _down_real_uplinks(host, switch)
        if not down or len(down) >= len(real_uplinks):
            continue
        kind = "DVS" if switch.is_distributed else "vSwitch"
        findings.append(
            Finding(
                rule_id="network.vswitch_uplink_link_down",
                title="Network switch uplink is configured but has no physical link",
                severity=Severity.HIGH,
                summary=(
                    f"{host.hostname}: {kind} '{switch.name}' lists "
                    f"{len(real_uplinks)} uplinks ({', '.join(real_uplinks)}), but "
                    f"the following show Link Status: Down -- {', '.join(down)} -- "
                    "this switch's redundancy is already reduced even though "
                    "esxcfg-vswitch -l alone looks healthy."
                ),
                evidence=[f"nicinfo.sh: {u} Link Status = Down" for u in down],
                affected_host=host.hostname,
                affected_object=switch.name,
                remediation=(
                    "Check the physical cable/SFP/transceiver and upstream switch "
                    "port for the named uplink NIC(s); this is a link-layer problem, "
                    "not an ESXi configuration issue."
                ),
                limitations=(
                    "A point-in-time snapshot from the bundle's capture moment; a "
                    "link that recovered after capture is not reflected. Requires "
                    "both esxcfg-vswitch -l and nicinfo.sh data in the bundle."
                ),
            )
        )
    return findings


def _vswitch_all_uplinks_down(host: HostInfo) -> list[Finding]:
    findings = []
    for switch in host.network_switches:
        real_uplinks, down = _down_real_uplinks(host, switch)
        if not down or len(down) < len(real_uplinks):
            continue
        kind = "DVS" if switch.is_distributed else "vSwitch"
        findings.append(
            Finding(
                rule_id="network.vswitch_all_uplinks_down",
                title="All of a network switch's uplinks have no physical link",
                severity=Severity.CRITICAL,
                summary=(
                    f"{host.hostname}: {kind} '{switch.name}' has "
                    f"{len(real_uplinks)} configured uplink(s) ({', '.join(down)}), "
                    "and every one of them reports Link Status: Down -- everything "
                    "on this switch is currently without network connectivity."
                ),
                evidence=[f"nicinfo.sh: {u} Link Status = Down" for u in down],
                affected_host=host.hostname,
                affected_object=switch.name,
                remediation=(
                    "Check the physical cable/SFP/transceiver and upstream switch "
                    "port for every uplink NIC on this switch immediately; any VM "
                    "port group on it is likely already affected."
                ),
                limitations=(
                    "A point-in-time snapshot from the bundle's capture moment; a "
                    "link that recovered after capture is not reflected."
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
    Rule(
        rule_id="network.vswitch_uplink_link_down",
        title="Network switch uplink is configured but has no physical link",
        default_severity=Severity.HIGH,
        evidence_required=("network_switches[].uplinks", "nic_adapters[].link_up"),
        limitations=(
            "Point-in-time snapshot at capture only; requires both esxcfg-vswitch -l "
            "and nicinfo.sh data in the bundle."
        ),
        evaluate=_vswitch_uplink_link_down,
    ),
    Rule(
        rule_id="network.vswitch_all_uplinks_down",
        title="All of a network switch's uplinks have no physical link",
        default_severity=Severity.CRITICAL,
        evidence_required=("network_switches[].uplinks", "nic_adapters[].link_up"),
        limitations="Point-in-time snapshot at capture only.",
        evaluate=_vswitch_all_uplinks_down,
    ),
]
