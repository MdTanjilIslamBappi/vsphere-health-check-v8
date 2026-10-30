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

**Configurable scope.** A retained log rotation can span well over a year
on a quiet host. This assessment is a point-in-time health check, so only
log lines timestamped within the last ``host.log_window_weeks`` (1-26,
default 13 -- see ``AssessmentConfig.log_window_weeks`` / ``vhealth
assess --weeks``) weeks of the bundle's own capture date count toward
findings in ``log_signal_counts`` -- older matches are tallied separately
in ``log_signal_counts_excluded`` rather than discarded outright, so
nothing is silently lost, but they do not drive an active finding in a
report scoped to that window. A line with no parseable leading
timestamp, or a bundle with no parseable capture date, is treated as
in-window rather than guessed away.
"""

from __future__ import annotations

import gzip
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "3.0.0"

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

_LINE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T")
_CAPTURED_ON_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    warnings: list[str] = []
    log_dir = host_dir / "var" / "run" / "log"
    if not log_dir.is_dir():
        return ["var/run/log not found; log-based signals unavailable"]

    cutoff = _window_cutoff(host.captured_on, host.log_window_weeks)
    if cutoff is None:
        warnings.append(
            "Could not determine the bundle's capture date; log signals were not filtered "
            f"to the configured {host.log_window_weeks}-week window."
        )

    found_any_rotation = False
    for stem, signals in (("vmkwarning", _VMKWARNING_SIGNALS), ("vobd", _VOBD_SIGNALS)):
        matched_rotation = _scan_rotations(log_dir, stem, signals, host, cutoff)
        found_any_rotation = found_any_rotation or matched_rotation

    host.log_data_available = found_any_rotation
    if not found_any_rotation:
        warnings.append(
            "No vmkwarning/vobd rotations found; storage/hardware log signals unavailable"
        )
    return warnings


def _window_cutoff(captured_on: str | None, window_weeks: int) -> date | None:
    if not captured_on:
        return None
    match = _CAPTURED_ON_DATE_RE.match(captured_on)
    if not match:
        return None
    try:
        captured_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None
    return captured_date - timedelta(weeks=window_weeks)


def _line_date(line: str) -> date | None:
    match = _LINE_DATE_RE.match(line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _scan_rotations(
    log_dir: Path,
    stem: str,
    signals: dict[str, re.Pattern[str]],
    host: HostInfo,
    cutoff: date | None,
) -> bool:
    found_any = False
    for i in range(_MAX_ROTATIONS):
        for candidate in (log_dir / f"{stem}.{i}.gz", log_dir / f"{stem}.{i}"):
            if not candidate.is_file():
                continue
            found_any = True
            text = _read_text(candidate)
            for line in text.splitlines():
                line_date = _line_date(line)
                in_window = cutoff is None or line_date is None or line_date >= cutoff
                for signal_name, pattern in signals.items():
                    if not pattern.search(line):
                        continue
                    if not in_window:
                        host.log_signal_counts_excluded[signal_name] = (
                            host.log_signal_counts_excluded.get(signal_name, 0) + 1
                        )
                        continue
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
