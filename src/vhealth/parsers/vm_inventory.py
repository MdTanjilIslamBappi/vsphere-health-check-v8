"""Parse the host's own record of its currently-running VMs.

Source: ``commands/localcli_vm-process-list.txt`` (``localcli vm process
list``). This is a genuinely different data source from vCenter's
inventory database: it is the ESXi host reporting what it is *actually
running right now*, not a copy of vCenter's registry. That means two
real limitations, both surfaced as an honest caveat in the report rather
than silently glossed over:

* Powered-off VMs never appear here -- vm-support captures no file that
  lists them. Only vCenter's own database has that.
* A VM with no running world will not appear here even if registered on
  this host (e.g. mid-migration, or powered off between vMotions).
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo, VirtualMachine

VERSION = "1.0.0"

_FIELD_RE = re.compile(r"^\s*(World ID|Display Name|UUID|Config File):\s*(.*)$", re.MULTILINE)
_DATASTORE_UUID_RE = re.compile(r"^/vmfs/volumes/([^/]+)/")


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / "localcli_vm-process-list.txt"
    if not path.is_file():
        return ["localcli_vm-process-list.txt not found; running VM inventory unavailable"]

    text = path.read_text(encoding="utf-8", errors="replace")
    host.vm_inventory_available = True
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        fields = dict(_FIELD_RE.findall(block))
        name = fields.get("Display Name")
        if not name:
            continue
        config_path = fields.get("Config File") or None
        datastore_uuid = None
        if config_path and (match := _DATASTORE_UUID_RE.match(config_path)):
            datastore_uuid = match.group(1)
        host.virtual_machines.append(
            VirtualMachine(
                name=name,
                uuid=fields.get("UUID") or None,
                world_id=fields.get("World ID") or None,
                config_path=config_path,
                datastore_uuid=datastore_uuid,
            )
        )

    if not host.virtual_machines:
        return ["localcli_vm-process-list.txt present but no running VMs found in it"]
    return []
