"""Parse whether a host has an image profile staged for the next reboot.

Source: ``commands/localcli_software-profile-get---rebooting-image.txt``
-- the output of ``esxcli software profile get --rebooting-image``. On a
host with no pending update this literally reports a profile named
``No pending image profile available.``; a host that has applied an
update (VIBs staged) but was never rebooted reports the real pending
profile's name instead. This is a common, easily-missed operational
gap: patches look "installed" from the active profile alone, but are
not actually running until the host reboots.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_FILENAME = "localcli_software-profile-get---rebooting-image.txt"
_NAME_RE = re.compile(r"^ {3}Name: (.*)$")
_NO_PENDING_IMAGE = "No pending image profile available."


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; pending-reboot image state unavailable"]

    text = path.read_text(encoding="utf-8", errors="replace")
    name: str | None = None
    for line in text.splitlines():
        match = _NAME_RE.match(line)
        if match:
            name = match.group(1).strip()
            break
    if name is None:
        return [f"{_FILENAME} did not match the expected format"]

    host.pending_reboot_data_available = True
    host.pending_reboot_image_name = None if name == _NO_PENDING_IMAGE else name
    return []
