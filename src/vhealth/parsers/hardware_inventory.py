"""Parse physical server/CPU identity, management IP, and cluster membership.

Sources:

* ``commands/smbiosDump.txt`` -- the live SMBIOS table dump. The "System
  Info (Type 1)" record gives the server manufacturer/model; the first
  "Processor Info (Type 4)" record whose status is populated/enabled gives
  the CPU model string. Both are vendor-firmware text, stable across the
  ESXi releases this tool has been validated against.
* ``commands/esxcfg-vmknic_-l.txt`` -- the VMkernel NIC table. ``vmk0`` is
  used as the management interface IP; this is a convention, not a
  guarantee (see limitations in SUPPORTED_FORMATS.md).
* ``commands/clusterAdmin_cluster-status.txt`` -- JSON cluster-membership
  status as reported locally by the host's own cluster agent. This is
  host-reported data, not a read of vCenter's cluster/EVC configuration --
  it cannot tell you EVC mode, HA admission control, or alarms, only
  whether this host currently reports itself a member of a compute
  resource and whether its local agent is in an alarm state.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_SYSTEM_INFO_RE = re.compile(
    r'System Info \(Type 1\):.*?\n\s*Manufacturer:\s*"([^"]*)"\s*\n\s*Product:\s*"([^"]*)"',
    re.DOTALL,
)
_PROCESSOR_INFO_RE = re.compile(
    r'Processor Info \(Type 4\):.*?\n'
    r'(?:.*\n)*?\s*Socket Status:\s*(.+?)\s*\n'
    r'(?:.*\n)*?\s*Manufacturer:\s*"([^"]*)"\s*\n'
    r'\s*Version:\s*"([^"]*)"',
)


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    warnings: list[str] = []

    smbios_path = host_dir / "commands" / "smbiosDump.txt"
    if smbios_path.is_file():
        text = smbios_path.read_text(encoding="utf-8", errors="replace")
        _parse_smbios(text, host)
    else:
        warnings.append("smbiosDump.txt not found; server/CPU model unknown")

    vmknic_path = host_dir / "commands" / "esxcfg-vmknic_-l.txt"
    if vmknic_path.is_file():
        text = vmknic_path.read_text(encoding="utf-8", errors="replace")
        host.management_ip = _find_vmk0_ip(text)
    else:
        warnings.append("esxcfg-vmknic_-l.txt not found; management IP unknown")

    cluster_path = host_dir / "commands" / "clusterAdmin_cluster-status.txt"
    if cluster_path.is_file():
        text = cluster_path.read_text(encoding="utf-8", errors="replace")
        _parse_cluster_status(text, host)

    return warnings


def _parse_smbios(text: str, host: HostInfo) -> None:
    if match := _SYSTEM_INFO_RE.search(text):
        host.server_manufacturer = match.group(1).strip() or None
        host.server_model = match.group(2).strip() or None

    sockets = 0
    cpu_model = None
    for match in _PROCESSOR_INFO_RE.finditer(text):
        status, manufacturer, version = match.groups()
        status_lower = status.strip().lower()
        if not status_lower.startswith("populated") or "disabled" in status_lower:
            continue
        sockets += 1
        if cpu_model is None:
            cpu_model = version.strip() or f"{manufacturer.strip()} (model unknown)"
    if sockets:
        host.cpu_sockets = sockets
        host.cpu_model = cpu_model


def _find_vmk0_ip(text: str) -> str | None:
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0] != "vmk0":
            continue
        if "IPv4" not in parts:
            continue
        idx = parts.index("IPv4")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _parse_cluster_status(text: str, host: HostInfo) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return
    if data.get("is_in_cluster"):
        host.cluster_id = data.get("cluster_id")
    host.cluster_in_alarm = data.get("is_in_alarm")
