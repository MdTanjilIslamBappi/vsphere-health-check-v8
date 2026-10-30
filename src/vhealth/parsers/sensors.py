"""Parse IPMI hardware sensors (fans, temperature, voltage, PSU, ...).

Source: ``commands/localcli_hardware-ipmi-sdr-list--p--i--n-all.txt``, a
fixed-width table with columns including Description, Computed Reading,
Base Unit and Sensor Type.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HardwareSensor, HostInfo
from vhealth.parsers.table_utils import parse_fixed_width_table

VERSION = "1.0.0"

_FILENAME = "localcli_hardware-ipmi-sdr-list--p--i--n-all.txt"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    sdr_path = host_dir / "commands" / _FILENAME
    if not sdr_path.is_file():
        return [
            f"{_FILENAME} not found; IPMI hardware sensors unavailable (no BMC, or host is a VM)"
        ]

    text = sdr_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_fixed_width_table(text)
    if not rows:
        return [f"{_FILENAME} did not match the expected table format"]

    for row in rows:
        reading = row.get("Computed Reading", "")
        host.sensors.append(
            HardwareSensor(
                name=row.get("Description", "unknown"),
                reading=reading,
                unit=row.get("Base Unit"),
                sensor_type=row.get("Sensor Type"),
                status=_classify(reading),
            )
        )
    return []


def _classify(reading: str) -> str:
    normalized = reading.strip().lower()
    if normalized == "state asserted":
        return "asserted"
    if normalized == "state deasserted":
        return "deasserted"
    return "reading"
