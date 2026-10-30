"""Parse physical NIC link state (``nicinfo.sh`` output).

Source: ``commands/nicinfo.sh.txt`` -- a standard esxcli-style fixed-width
table (dashed separator row) listing every physical NIC ESXi knows
about, each with an Admin Status (administratively enabled/disabled)
and a separate Link Status (whether a cable is actually connected and
negotiated). A NIC can be Admin "Up" but Link "Down" simply because it
is an unused spare port with nothing plugged in -- that alone is not a
finding. It only becomes one when that same NIC is also a configured
vSwitch/DVS uplink (see ``network_rules.py``): a switch that lists two
uplinks for redundancy, but one of them has no actual link, has already
lost that redundancy even though ``esxcfg-vswitch -l`` alone looks fine.

The file has a lot of free-text detail (per-NIC driver info, module
parameters -- each with its own dashed-looking separator lines) *after*
the one table this parser cares about, separated from it by a blank
line; ``table_utils.parse_fixed_width_table`` has no notion of where a
table ends, so the main table block is sliced out first.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo, NetworkAdapter
from vhealth.parsers.table_utils import parse_fixed_width_table

VERSION = "1.0.0"

_FILENAME = "nicinfo.sh.txt"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; physical NIC link state unavailable"]

    table_text = _main_table(path.read_text(encoding="utf-8", errors="replace"))
    rows = parse_fixed_width_table(table_text)
    if not rows:
        return [f"{_FILENAME} did not match the expected table format"]

    adapters = [
        NetworkAdapter(name=row["Name"], link_up=row.get("Link Status") == "Up")
        for row in rows
        if row.get("Name")
    ]
    if not adapters:
        return [f"{_FILENAME} did not match the expected table format"]

    host.nic_data_available = True
    host.nic_adapters = adapters
    return []


def _main_table(text: str) -> str:
    """Slice out just the header+separator+data-row block, stopping at the

    first blank line after it (everything past that is per-NIC detail,
    not more table rows).
    """
    lines = text.splitlines()
    header_idx = None
    for i in range(len(lines) - 1):
        candidate = lines[i + 1].strip()
        if len(candidate) > 3 and set(candidate) <= {"-", " "}:
            header_idx = i
            break
    if header_idx is None:
        return text

    end = len(lines)
    for j in range(header_idx + 2, len(lines)):
        if not lines[j].strip():
            end = j
            break
    return "\n".join(lines[header_idx:end])
