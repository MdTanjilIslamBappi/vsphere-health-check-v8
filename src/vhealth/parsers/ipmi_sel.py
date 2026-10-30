"""Scan the IPMI System Event Log (SEL) history for known hardware signals.

Source: ``commands/localcli_hardware-ipmi-sel-list--p--i--n-all.txt`` -- a
block-style dump (not a fixed-width table): each SEL record is a
non-indented ``Record:N:`` header line followed by indented ``Key: Value``
lines, including ``When`` (the event's own timestamp) and ``Message``
(e.g. ``Assert + Memory Uncorrectable ECC``). Unlike
``hardware.ipmi_sensor_asserted`` (``sensors.py``), which only reports the
*current* sensor state from ``ipmi sdr list``, the SEL is historical -- a
transient event that already cleared itself (a drive pulled and replaced,
a brief PSU blip) still shows up here even though the current sensor
reading is clean again.

Only ``Assert +`` records are considered (a ``Deassert`` means the
condition cleared, not a new problem), and only a hand-picked set of
unambiguous hardware-failure message types is tracked -- generic/noisy
SEL entries (boot/shutdown, log-area-reset housekeeping, chassis
intrusion, which fires routinely during legitimate maintenance access,
and ambiguous paired redundancy-state transitions) are intentionally not
reported on, to avoid flooding a report with routine BMC chatter.

**Quarterly scope.** Same convention as ``vmk_log.py``: only SEL records
timestamped within the last ``_WINDOW_DAYS`` (90) days of the bundle's
own capture date count toward an active finding (``host.log_signal_counts``);
older matches are tallied in ``host.log_signal_counts_excluded`` instead,
and both share those fields with ``vmk_log.py``'s own signals (distinct
key names keep the two sources from colliding).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_FILENAME = "localcli_hardware-ipmi-sel-list--p--i--n-all.txt"
_FIELD_RE = re.compile(r"^ {3}([^:]+):\s?(.*)$")
_WHEN_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T")
_CAPTURED_ON_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_WINDOW_DAYS = 90
_MAX_EXAMPLES_PER_SIGNAL = 5

_SEL_SIGNALS: dict[str, re.Pattern[str]] = {
    "sel_ecc_uncorrectable": re.compile(r"^Assert \+ Memory Uncorrectable ECC"),
    "sel_drive_predictive_failure": re.compile(r"^Assert \+ Drive Slot Predictive Failure"),
    "sel_psu_failure": re.compile(r"^Assert \+ Power Supply Failure status"),
    "sel_temperature_critical": re.compile(r"^Assert \+ Temperature Upper Critical"),
}


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; IPMI SEL event history unavailable"]

    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = _split_blocks(text)
    if not blocks:
        return [f"{_FILENAME} did not match the expected block format"]

    cutoff = _quarterly_cutoff(host.captured_on)
    for block in blocks:
        message = block.get("Message", "")
        when = block.get("When", "")
        for signal_name, pattern in _SEL_SIGNALS.items():
            if not pattern.match(message):
                continue
            event_date = _parse_date(when)
            in_window = cutoff is None or event_date is None or event_date >= cutoff
            if not in_window:
                host.log_signal_counts_excluded[signal_name] = (
                    host.log_signal_counts_excluded.get(signal_name, 0) + 1
                )
                continue
            host.log_signal_counts[signal_name] = host.log_signal_counts.get(signal_name, 0) + 1
            examples = [e for e in host.log_events if e.startswith(f"[{signal_name}]")]
            if len(examples) < _MAX_EXAMPLES_PER_SIGNAL:
                host.log_events.append(f"[{signal_name}] {when} - {message.strip()}")
    return []


def _quarterly_cutoff(captured_on: str | None) -> date | None:
    if not captured_on:
        return None
    match = _CAPTURED_ON_DATE_RE.match(captured_on)
    if not match:
        return None
    try:
        captured_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None
    return captured_date - timedelta(days=_WINDOW_DAYS)


def _parse_date(when: str) -> date | None:
    match = _WHEN_DATE_RE.match(when)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _split_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _FIELD_RE.match(line)
        if match and current is not None:
            current[match.group(1).strip()] = match.group(2).strip()
            continue
        # Any non-indented, non-blank line is a new record-block header.
        current = {}
        blocks.append(current)
    return blocks
