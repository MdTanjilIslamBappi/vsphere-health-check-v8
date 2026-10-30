"""Parse host NTP time-synchronization status.

Source: ``commands/localcli_--formatterjson-system-ntp-get.txt`` -- the
JSON output of ``esxcli system ntp get``. This reports ``Enabled`` (the
NTP client service state), ``Servers`` (configured server list), and
``Time Synchronized`` -- whether the clock is actually synchronized right
now. The last is the field worth checking: a host can have NTP enabled
with a server configured and still never actually sync (e.g. an
unreachable or misconfigured server), which this parser surfaces as its
own field rather than inferring sync state from ``Enabled`` alone.
"""

from __future__ import annotations

import json
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_NTP_GET_FILENAME = "localcli_--formatterjson-system-ntp-get.txt"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    warnings: list[str] = []

    ntp_path = host_dir / "commands" / _NTP_GET_FILENAME
    if not ntp_path.is_file():
        warnings.append(f"{_NTP_GET_FILENAME} not found; NTP sync status unknown")
        return warnings

    text = ntp_path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        warnings.append(f"{_NTP_GET_FILENAME} could not be parsed as JSON")
        return warnings

    if not isinstance(data, dict):
        warnings.append(f"{_NTP_GET_FILENAME} did not contain the expected object")
        return warnings

    host.ntp_data_available = True
    host.ntp_enabled = data.get("Enabled")
    host.ntp_time_synchronized = data.get("Time Synchronized")
    servers = data.get("Servers")
    if isinstance(servers, list):
        host.ntp_servers = [str(s) for s in servers]

    return warnings
