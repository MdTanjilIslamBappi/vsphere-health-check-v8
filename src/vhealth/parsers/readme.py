"""Parse the top-level vm-support README for capture metadata.

Format (stable since ESXi 6.x)::

    Captured on: 2026-10-27 08:00:21.302877
    vm-support version: v4.1
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_CAPTURED_ON_RE = re.compile(r"^Captured on:\s*(.+)$", re.MULTILINE)
_VM_SUPPORT_VERSION_RE = re.compile(r"^vm-support version:\s*(.+)$", re.MULTILINE)


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    readme_path = host_dir / "README"
    if not readme_path.is_file():
        return ["README not found; capture metadata is unavailable"]

    text = readme_path.read_text(encoding="utf-8", errors="replace")

    if match := _CAPTURED_ON_RE.search(text):
        host.captured_on = match.group(1).strip()
    if match := _VM_SUPPORT_VERSION_RE.search(text):
        host.vm_support_version = match.group(1).strip()

    return []
