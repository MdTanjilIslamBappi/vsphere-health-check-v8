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

Each VM's own ``vmware.log`` (alongside its ``.vmx``, found via the
``Config File`` path above) is also checked for the documented
``FeatureCompat: No EVC masks.`` line that VMware's vmx process writes
at every power-on -- real evidence of whether an EVC CPU-feature mask is
being applied, independent of vCenter. This is *not* a read of the
cluster's configured EVC baseline name (confirmed, by direct inspection
of a real vCenter support bundle, to exist nowhere in either bundle
type); it only answers whether a mask is active right now, and only
when the line is actually found -- its absence is inconclusive, not
evidence that a mask *is* applied, so it is never reported as such.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo, VirtualMachine

VERSION = "1.1.0"

_FIELD_RE = re.compile(r"^\s*(World ID|Display Name|UUID|Config File):\s*(.*)$", re.MULTILINE)
_DATASTORE_UUID_RE = re.compile(r"^/vmfs/volumes/([^/]+)/")
_NO_EVC_MASKS_LINE = "FeatureCompat: No EVC masks."
_MAX_LOG_ROTATIONS_CHECKED = 10
_LOG_READ_BYTES = 262_144  # the FeatureCompat section is logged near the top of each boot


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
        vm = VirtualMachine(
            name=name,
            uuid=fields.get("UUID") or None,
            world_id=fields.get("World ID") or None,
            config_path=config_path,
            datastore_uuid=datastore_uuid,
        )
        vm.no_evc_masks_observed = _check_no_evc_masks(host_dir, config_path)
        host.virtual_machines.append(vm)

    if not host.virtual_machines:
        return ["localcli_vm-process-list.txt present but no running VMs found in it"]
    return []


def _check_no_evc_masks(host_dir: Path, config_path: str | None) -> bool:
    """Look for the "No EVC masks." power-on line in a VM's vmware.log/rotations."""
    if not config_path or not config_path.startswith("/vmfs/volumes/"):
        return False
    vm_dir = host_dir / Path(config_path).parent.relative_to("/")
    candidates = [vm_dir / "vmware.log"]
    candidates += [vm_dir / f"vmware-{i}.log" for i in range(_MAX_LOG_ROTATIONS_CHECKED)]
    for log_path in candidates:
        if not log_path.is_file():
            continue
        try:
            with log_path.open(encoding="utf-8", errors="replace") as f:
                chunk = f.read(_LOG_READ_BYTES)
        except OSError:
            continue
        if _NO_EVC_MASKS_LINE in chunk:
            return True
    return False
