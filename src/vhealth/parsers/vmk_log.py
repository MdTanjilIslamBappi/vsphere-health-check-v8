"""Scan rotated vmkernel-warning and VOB logs for known storage/hardware signals.

ESXi does not always retain a plain-text ``vmkernel.log`` in a vm-support
bundle (recent releases can store it in the binary VLF format, which this
tool does not decode -- see SUPPORTED_FORMATS.md). ``vmkwarning.*`` carries
the WARNING-level subset of the same stream and is reliably present in
plain text, so it is used as the primary source; ``vobd.*`` (VMkernel
Observation events) is scanned for ``esx.problem.*`` events as a second,
independent signal.

Only a bounded number of representative example lines per signal are kept
(``_MAX_EXAMPLES_PER_SIGNAL``) so the assessment output stays a reasonable
size for a host with a long, noisy log history; the full occurrence count
is still recorded.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_MAX_EXAMPLES_PER_SIGNAL = 5
_MAX_ROTATIONS = 8

_VMKWARNING_SIGNALS: dict[str, re.Pattern[str]] = {
    "pdl_error": re.compile(r"PDL error|nmp_PathDetermineFailure", re.I),
    "alua_no_connection": re.compile(
        r"Could not get page 83 INQUIRY data for path .* - No connection", re.I
    ),
    "apd_event": re.compile(r"\bAPD\b.*(timeout|state|device)", re.I),
    "path_dead": re.compile(r"\b(Device|Path)\b.*\bis\s+dead\b", re.I),
}

_VOBD_SIGNALS: dict[str, re.Pattern[str]] = {
    "vob_storage_problem": re.compile(r"esx\.problem\.(storage|scsi|vmfs|vob\.storage)", re.I),
}


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    warnings: list[str] = []
    log_dir = host_dir / "var" / "run" / "log"
    if not log_dir.is_dir():
        return ["var/run/log not found; log-based signals unavailable"]

    found_any_rotation = False
    for stem, signals in (("vmkwarning", _VMKWARNING_SIGNALS), ("vobd", _VOBD_SIGNALS)):
        matched_rotation = _scan_rotations(log_dir, stem, signals, host)
        found_any_rotation = found_any_rotation or matched_rotation

    host.log_data_available = found_any_rotation
    if not found_any_rotation:
        warnings.append(
            "No vmkwarning/vobd rotations found; storage/hardware log signals unavailable"
        )
    return warnings


def _scan_rotations(
    log_dir: Path,
    stem: str,
    signals: dict[str, re.Pattern[str]],
    host: HostInfo,
) -> bool:
    found_any = False
    for i in range(_MAX_ROTATIONS):
        for candidate in (log_dir / f"{stem}.{i}.gz", log_dir / f"{stem}.{i}"):
            if not candidate.is_file():
                continue
            found_any = True
            text = _read_text(candidate)
            for line in text.splitlines():
                for signal_name, pattern in signals.items():
                    if pattern.search(line):
                        host.log_signal_counts[signal_name] = (
                            host.log_signal_counts.get(signal_name, 0) + 1
                        )
                        examples = [
                            e for e in host.log_events if e.startswith(f"[{signal_name}]")
                        ]
                        if len(examples) < _MAX_EXAMPLES_PER_SIGNAL:
                            host.log_events.append(f"[{signal_name}] {line.strip()[:300]}")
    return found_any


def _read_text(path: Path) -> str:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as f:
                return f.read().decode("utf-8", errors="replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
