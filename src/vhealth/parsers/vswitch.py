"""Parse standard vSwitch and distributed virtual switch (DVS) configuration.

Source: ``commands/esxcfg-vswitch_-l.txt``. Unlike most esxcli/localcli
output, this command's tables have no dashed separator row and are not
reliably fixed-width either: each switch is a two-line stanza -- a
header naming its columns, immediately followed by exactly one data row
for the switch itself -- then that switch's portgroup/DVPort sub-table,
which this parser ignores entirely (it only reacts to lines that open a
new switch stanza). A switch name longer than the tool's normal column
width is not truncated or re-padded, which shifts every later column in
that one data row to the right of where a fixed header-offset slice
would expect it (confirmed in real data: a 22-character DVS name on a
real host pushes its MTU/Uplinks values several characters right of
where short names put them). Splitting the data row on runs of 2+
whitespace characters survives that, since none of these columns'
values (ports, MTU, comma-joined uplink names) ever contain internal
whitespace themselves.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo, NetworkSwitch

VERSION = "1.0.0"

_FILENAME = "esxcfg-vswitch_-l.txt"
_FIELD_SPLIT_RE = re.compile(r"\s{2,}")
# Fixed column order after the switch name: Num Ports, Used Ports,
# Configured Ports, MTU, Uplinks (the last is omitted entirely, not left
# blank, when a switch has no uplinks at all).
_USED_PORTS_INDEX = 1
_MTU_INDEX = 3
_UPLINKS_INDEX = 4


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; vSwitch/DVS configuration unknown"]

    text = path.read_text(encoding="utf-8", errors="replace")
    switches = _parse_switches(text)
    if not switches:
        return [f"{_FILENAME} did not match the expected format"]

    host.network_switch_data_available = True
    host.network_switches = switches
    return []


def _parse_switches(text: str) -> list[NetworkSwitch]:
    lines = text.splitlines()
    switches: list[NetworkSwitch] = []
    for i, line in enumerate(lines):
        is_dvs = line.startswith("DVS Name")
        if not (is_dvs or line.startswith("Switch Name")) or i + 1 >= len(lines):
            continue
        data_line = lines[i + 1].strip()
        if not data_line:
            continue
        fields = _FIELD_SPLIT_RE.split(data_line)
        name, rest = fields[0], fields[1:]
        if not name:
            continue
        used_ports = rest[_USED_PORTS_INDEX] if len(rest) > _USED_PORTS_INDEX else ""
        mtu = rest[_MTU_INDEX] if len(rest) > _MTU_INDEX else ""
        uplinks = rest[_UPLINKS_INDEX] if len(rest) > _UPLINKS_INDEX else ""
        switches.append(
            NetworkSwitch(
                name=name,
                is_distributed=is_dvs,
                mtu=int(mtu) if mtu.isdigit() else None,
                used_ports=int(used_ports) if used_ports.isdigit() else None,
                uplinks=[u.strip() for u in uplinks.split(",") if u.strip()],
            )
        )
    return switches
