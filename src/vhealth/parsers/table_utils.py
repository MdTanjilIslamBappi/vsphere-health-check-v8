"""Helpers for parsing ESXi CLI fixed-width and JSON command output."""

from __future__ import annotations

import json
import re
from pathlib import Path


def parse_fixed_width_table(text: str) -> list[dict[str, str]]:
    """Parse an esxcli-style ASCII table using its dashed separator line.

    ESXi ``localcli``/``esxcli`` plain-text tables print a header row
    followed by a row of dashes whose runs mark each column's width; data
    rows are then sliced at those same character offsets. This is more
    reliable than splitting on whitespace because free-text columns (e.g.
    a sensor description) can legitimately contain runs of spaces.
    """
    lines = text.splitlines()
    header_idx = _find_separator_row(lines)
    if header_idx is None:
        return []

    header, sep = lines[header_idx], lines[header_idx + 1]
    spans = [(m.start(), m.end()) for m in re.finditer(r"-+", sep)]
    columns = [header[s:e].strip() for s, e in spans]

    rows: list[dict[str, str]] = []
    for line in lines[header_idx + 2 :]:
        if not line.strip():
            continue
        row = {}
        for idx, (start, end) in enumerate(spans):
            stop = len(line) if idx == len(spans) - 1 else min(end, len(line))
            row[columns[idx]] = line[start:stop].strip() if start < len(line) else ""
        rows.append(row)
    return rows


def _find_separator_row(lines: list[str]) -> int | None:
    for i in range(len(lines) - 1):
        candidate = lines[i + 1].strip()
        if len(candidate) > 3 and set(candidate) <= {"-", " "}:
            return i
    return None


def load_json_array(path: Path) -> list[dict]:
    """Load a localcli JSON-output file, tolerating empty/invalid content."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []
