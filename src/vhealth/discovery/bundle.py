"""Locate individual ESXi vm-support host bundles and vCenter (vc-support)
bundles within an extracted tree.

A vCenter support bundle contains one such directory per host (after the
nested .tgz members have been expanded by the ingestion stage); a single
ESXi host bundle contains exactly one. Real vCenter bundle downloads
also usually contain one top-level ``vc-support`` .tgz member for the
vCenter Server appliance itself; its root directory (``vc-<fqdn>-...``)
also has a ``README`` and ``commands/`` for structural reasons, so it
must be excluded from host discovery and parsed separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class HostBundleRef:
    root: Path
    hostname_hint: str


@dataclass
class VCenterBundleRef:
    root: Path
    hostname_hint: str


_MARKERS_FILENAME = "README"
_MARKER_DIRNAME = "commands"


def find_host_bundles(extracted_root: Path) -> list[HostBundleRef]:
    """Find directories that look like an ESXi vm-support bundle root.

    A vm-support bundle root is identified by containing both a top-level
    ``README`` file and a ``commands/`` directory -- the one structural
    marker that has been stable across the ESXi releases this tool has
    been validated against (see SUPPORTED_FORMATS.md).

    Directories identified as vCenter Server appliance bundles are
    excluded here; they are located separately by ``find_vcenter_bundles``.
    """
    candidates: list[HostBundleRef] = []
    for readme in extracted_root.rglob(_MARKERS_FILENAME):
        host_dir = readme.parent
        if not (host_dir / _MARKER_DIRNAME).is_dir():
            continue
        if _is_vcenter_bundle_dir(host_dir, readme):
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


def find_vcenter_bundles(extracted_root: Path) -> list[VCenterBundleRef]:
    """Find directories that look like a vCenter ``vc-support`` bundle root."""
    candidates: list[VCenterBundleRef] = []
    for readme in extracted_root.rglob(_MARKERS_FILENAME):
        bundle_dir = readme.parent
        if not (bundle_dir / _MARKER_DIRNAME).is_dir():
            continue
        if _is_vcenter_bundle_dir(bundle_dir, readme):
            candidates.append(
                VCenterBundleRef(root=bundle_dir, hostname_hint=_guess_vcenter_hostname(bundle_dir))
            )

    seen: set[Path] = set()
    unique: list[VCenterBundleRef] = []
    for ref in candidates:
        resolved = ref.root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(ref)
    return unique


def _is_vcenter_bundle_dir(bundle_dir: Path, readme_path: Path) -> bool:
    """Decide whether a README+commands directory is a vCenter appliance bundle.

    The authoritative marker is the vc-support README's Command line
    line -- it launched ``vc-support`` while an ESXi bundle launches
    ``vm-support``/``vm-support.cgi`` (an ESXi README never mentions
    vc-support). The ``vc-`` directory-name prefix is used as a fallback
    for bundles whose README is unreadable.
    """
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")[:2048]
    except OSError:
        text = ""
    first_line = text.split("\n", 1)[0]
    if first_line.startswith("Command line: vc-support"):
        return True
    return _guess_vcenter_hostname(bundle_dir) is not None


def _guess_vcenter_hostname(bundle_dir: Path) -> str | None:
    """vc-support directories are named like ``vc-<FQDN>-<timestamp>-<pid>``."""
    name = bundle_dir.name
    if not name.startswith("vc-"):
        return None
    name = name[len("vc-") :]
    parts = name.split("-")
    return parts[0] if parts else None


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
