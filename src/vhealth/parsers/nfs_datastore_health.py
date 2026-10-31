"""Parse ESXi's own built-in NFS-datastore-health verdict.

Source: ``var/lib/vmware/osdata/healthd/vmw.nfsDatastoreHealth-*.json``
(see ``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). Unlike ``vmw.memoryHealth``, this check's ``unstructured``
section is a *list* -- one entry per NFS datastore mount known to this
host, each with ESXi's own ``is_accessible``/``is_mounted`` verdict, not
something vhealth infers. A host with no NFS datastores configured at
all reports an empty list (nothing to assess), which this parser
represents the same way as "no NFS datastores" -- distinct from one
configured but currently inaccessible/unmounted.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo, NfsDatastoreHealth
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.nfsDatastoreHealth"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    if not isinstance(unstructured, list):
        warnings.append(
            "Most recent vmw.nfsDatastoreHealth snapshot had no 'unstructured' list"
        )
        return warnings

    datastores = [d for d in (_parse_entry(e) for e in unstructured) if d is not None]
    host.nfs_health_data_available = True
    host.nfs_datastores = datastores
    return warnings


def _parse_entry(entry: object) -> NfsDatastoreHealth | None:
    if not isinstance(entry, dict):
        return None
    volume_name = entry.get("volume_name")
    if not volume_name:
        return None
    remote_hosts = entry.get("remote_host(s)")
    return NfsDatastoreHealth(
        volume_name=str(volume_name),
        remote_share_name=entry.get("remote_share_name") or None,
        remote_hosts=[str(h) for h in remote_hosts] if isinstance(remote_hosts, list) else [],
        version=entry.get("version") or None,
        is_accessible=bool(entry.get("is_accessible", True)),
        is_mounted=bool(entry.get("is_mounted", True)),
        is_read_only=bool(entry.get("is_read_only", False)),
        inaccessible_reason=entry.get("inaccessible_reason") or None,
    )
