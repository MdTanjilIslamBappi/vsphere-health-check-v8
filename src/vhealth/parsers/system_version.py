"""Parse ESXi product version/build and hostname.

Sources:

* ``commands/localcli_system-version-get.txt`` -- ``Version``/``Update``/
  ``Patch``/``Build`` fields.
* ``commands/uname_-a.txt`` -- second whitespace-separated token is the
  hostname, as captured by the kernel at the time of the support bundle.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_FIELD_RE = re.compile(r"^\s*(Version|Update|Patch|Build):\s*(.+)$", re.MULTILINE)


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    warnings: list[str] = []

    version_path = host_dir / "commands" / "localcli_system-version-get.txt"
    if version_path.is_file():
        text = version_path.read_text(encoding="utf-8", errors="replace")
        fields = {m.group(1): m.group(2).strip() for m in _FIELD_RE.finditer(text)}
        version = fields.get("Version")
        update = fields.get("Update")
        if version:
            host.esxi_version = f"{version} Update {update}" if update else version
        host.esxi_build = fields.get("Build")
    else:
        warnings.append("localcli_system-version-get.txt not found; ESXi version unknown")

    uname_path = host_dir / "commands" / "uname_-a.txt"
    if uname_path.is_file():
        tokens = uname_path.read_text(encoding="utf-8", errors="replace").split()
        if len(tokens) >= 2:
            host.hostname = tokens[1]
    else:
        warnings.append("uname_-a.txt not found; hostname taken from bundle directory name")

    return warnings
