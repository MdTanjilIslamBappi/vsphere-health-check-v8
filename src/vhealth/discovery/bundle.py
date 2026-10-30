"""Locate individual ESXi vm-support host bundles within an extracted tree.

A vCenter support bundle contains one such directory per host (after the
nested .tgz members have been expanded by the ingestion stage); a single
ESXi host bundle contains exactly one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class HostBundleRef:
    root: Path
    hostname_hint: str


_MARKER_FILENAME = "README"
_MARKER_DIRNAME = "commands"


def find_host_bundles(extracted_root: Path) -> list[HostBundleRef]:
    """Find directories that look like an ESXi vm-support bundle root.

    A vm-support bundle root is identified by containing both a top-level
    ``README`` file and a ``commands/`` directory -- the one structural
    marker that has been stable across the ESXi releases this tool has
    been validated against (see SUPPORTED_FORMATS.md).
    """
    candidates: list[HostBundleRef] = []
    for readme in extracted_root.rglob(_MARKER_FILENAME):
        host_dir = readme.parent
        if not (host_dir / _MARKER_DIRNAME).is_dir():
            continue
        candidates.append(HostBundleRef(root=host_dir, hostname_hint=_guess_hostname(host_dir)))

    # De-duplicate in case a bundle was discovered via more than one path.
    seen: set[Path] = set()
    unique: list[HostBundleRef] = []
    for ref in candidates:
        resolved = ref.root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(ref)
    return unique


def _guess_hostname(host_dir: Path) -> str:
    """Derive a hostname hint from the bundle directory name.

    vm-support directories are named like
    ``esx-<HOSTNAME>-<capture-timestamp>-<pid>``; this is only a fallback
    used before the README has been parsed for the authoritative value.
    """
    name = host_dir.name
    if name.startswith("esx-"):
        name = name[len("esx-") :]
    parts = name.split("-")
    return parts[0] if parts else name
