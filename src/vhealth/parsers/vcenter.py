"""Parsers for files inside a vCenter Server (``vc-support``) bundle.

Each parser enriches a ``vhealth.models.vcenter.VCenterInfo`` in place and
returns a list of warning strings. As with the ESXi parsers, malformed or
missing input must never raise -- missing evidence is recorded as a
warning so the rest of the assessment can proceed.

vc-support bundles mirror the VCSA appliance filesystem: ``README``,
``commands/*`` (the same command-name-mangling scheme as on ESXi), and
``var/log/vmware/*`` service log directories. Only appliance-level
identity, service status and filesystem usage are parsed here; the
vCenter database is not read.
"""

from __future__ import annotations

import re

from vhealth.models.vcenter import VCenterApplianceDisk, VCenterInfo

VERSION = "1.0.0"

_README_CAPTURE_PREFIX = "Captured on: "
_README_VERSION_PREFIX = "vm-support version: "

_KILOBYTE = 1024

_VPXD_RPM_LINE_PREFIXES = ("VMware-vpxd-", "vpxd-")

# Namespaces whose filesystem use is appliance-relevant. Everything else
# on the box (tmpfs, devtmpfs, overlay containers) is ignored for the
# appliance disk findings.
_VISIBLE_MOUNT_PREFIXES = ("/storage/",)


def parse(root, vcenter: VCenterInfo) -> list[str]:
    """Parse all supported vc-support sources into ``vcenter``, in place.

    ``root`` is the bundle root directory (the ``vc-<fqdn>-<timestamp>``
    directory), which contains ``README`` and ``commands/`` directly.
    """
    warnings: list[str] = []
    warnings += _parse_readme(root, vcenter)
    warnings += _parse_uname(root, vcenter)
    warnings += _parse_rpm(root, vcenter)
    warnings += _parse_service_control(root, vcenter)
    warnings += _parse_df(root, vcenter)
    warnings += _parse_vpxd_clusters(root, vcenter)
    return warnings


def _parse_readme(root, vcenter: VCenterInfo) -> list[str]:
    path = root / "README"
    if not path.is_file():
        return [
            "README not found; vCenter capture timestamp and vm-support version unavailable"
        ]
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith(_README_CAPTURE_PREFIX):
            vcenter.captured_on = line[len(_README_CAPTURE_PREFIX) :].strip()
        elif line.startswith(_README_VERSION_PREFIX):
            vcenter.vm_support_version = line[len(_README_VERSION_PREFIX) :].strip()
    return []


def _parse_uname(root, vcenter: VCenterInfo) -> list[str]:
    path = root / "commands" / "uname_-a.txt"
    if not path.is_file():
        return ["uname_-a.txt not found; vCenter hostname/kernel taken from bundle directory name"]
    text = path.read_text(encoding="utf-8", errors="replace")
    # e.g. "Linux vcsa01.example.test 5.10.252-4.ph4 #1-photon SMP ... x86_64 GNU/Linux"
    fields = text.split()
    if len(fields) >= 2:
        vcenter.hostname = fields[1]
        vcenter.hostname_source = "uname"
    vcenter.os_kernel = text.strip() or None
    return []


def _parse_rpm(root, vcenter: VCenterInfo) -> list[str]:
    path = root / "commands" / "rpm_-qa.txt"
    if not path.is_file():
        return ["rpm_-qa.txt not found; vCenter version/build unavailable"]
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        name = line.strip()
        if not name.startswith(_VPXD_RPM_LINE_PREFIXES):
            continue
        # Package names look like "VMware-vpxd-8.0.3.00900-15564605.x86_64".
        remainder = name.removesuffix(".x86_64").removesuffix(".noarch")
        parts = remainder.split("-")
        if len(parts) >= 2:
            version = parts[-2]
            build = parts[-1]
            if version and build.isdigit():
                vcenter.vc_version = version
                vcenter.vc_build = build
                return []
    return ["vpxd rpm entry not found in rpm_-qa.txt; vCenter version/build unavailable"]


def _parse_service_control(root, vcenter: VCenterInfo) -> list[str]:
    path = root / "commands" / "service-control_--status---all.txt"
    if not path.is_file():
        return [
            "service-control_--status---all.txt not found; appliance service status unavailable"
        ]
    text = path.read_text(encoding="utf-8", errors="replace")
    section: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and (
            stripped.lower().startswith("running") or stripped.lower().startswith("stopped")
        ):
            section = "running" if stripped.lower().startswith("running") else "stopped"
            continue
        if section == "running":
            vcenter.services_running.extend(stripped.split())
        elif section == "stopped":
            vcenter.services_stopped.extend(stripped.split())
    if not vcenter.services_running and not vcenter.services_stopped:
        return ["service-control output did not contain any service names"]
    return []


def _parse_df(root, vcenter: VCenterInfo) -> list[str]:
    path = root / "commands" / "df.txt"
    if not path.is_file():
        return ["df.txt not found; appliance filesystem usage unavailable"]
    text = path.read_text(encoding="utf-8", errors="replace")
    disks: list[VCenterApplianceDisk] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 6 or fields[0] == "Filesystem":
            continue
        mount = fields[5]
        is_root = mount == "/" and fields[0].startswith("/dev")
        if not (mount.startswith(_VISIBLE_MOUNT_PREFIXES) or is_root):
            continue
        percent = fields[4].removesuffix("%")
        if not percent.isdigit():
            continue
        disks.append(
            VCenterApplianceDisk(
                filesystem=fields[0],
                mount=fields[5],
                size_bytes=_kb_to_bytes(fields[1]),
                used_bytes=_kb_to_bytes(fields[2]),
                available_bytes=_kb_to_bytes(fields[3]),
                percent_used=int(percent),
            )
        )
    if not disks:
        return ["df.txt contained no parseable /storage/ mounts"]
    vcenter.appliance_disks = disks
    return []


def _kb_to_bytes(field: str) -> int | None:
    if not field.isdigit():
        return None
    return int(field) * _KILOBYTE


# Cluster names/membership are read from the *current, uncompressed*
# vpxd operational log (``var/log/vmware/vpxd/vpxd-<pid>.log``). vmomi
# managed objects appear in that log as name-tagged morefs such as
# ``[vim.ClusterComputeResource:domain-c1001,EAMSC2]``. Rotated .log.gz
# files, profiler logs, crash maps (-map-*) and dumps (drmdump/) are
# deliberately excluded.
_VPXD_LOG_GLOB = "var/log/vmware/vpxd/vpxd-*.log"

_CLUSTER_MOREF_RE = re.compile(
    r"\[vim\.ClusterComputeResource:(?P<moref>[A-Za-z0-9_.:-]+?),"
    r"(?P<name>[^\[\]\n]*?)\]"
)

# vCLS membership lines list the cluster moref followed by per-host
# chunks whose per-host morefs carry the member hostnames.
_VCLS_MEMBERSHIP_RE = re.compile(
    r"Dumping vCLS Pod Crx host infos; (?P<moref>domain-c\d+),"
)

_HOST_MOREF_RE = re.compile(
    r"\[vim\.HostSystem:(?:[A-Za-z0-9_.:-]+?),\s*(?P<hostname>[^\[\]\n,]+?)\]"
)

_CLUSTER_SCAN_CHUNK = 8 * 1024 * 1024
_CHUNK_OVERLAP = 4096
_MAX_TOTAL_SCAN_BYTES = 512 * 1024 * 1024


def _parse_vpxd_clusters(root, vcenter: VCenterInfo) -> list[str]:
    log_dir = root / "var" / "log" / "vmware" / "vpxd"
    if not log_dir.is_dir():
        return ["vpxd logs not present; vCenter cluster inventory unavailable"]
    logs = sorted(
        p
        for p in log_dir.glob(_VPXD_LOG_GLOB.rsplit("/", 1)[-1])
        if p.is_file() and p.stat().st_size > 0 and re.fullmatch(r"vpxd-\d+\.log", p.name)
    )
    if not logs:
        return ["no current (uncompressed) vpxd log found; vCenter cluster inventory unavailable"]
    total = sum(p.stat().st_size for p in logs)
    if total > _MAX_TOTAL_SCAN_BYTES:
        return [
            f"vpxd logs too large to scan ({total} bytes > {_MAX_TOTAL_SCAN_BYTES}); "
            "vCenter cluster inventory unavailable"
        ]
    for path in logs:
        _scan_vpxd_log_for_clusters(path, vcenter)
    if not vcenter.cluster_names:
        return ["vpxd log contained no cluster inventory evidence"]
    return []


def _scan_vpxd_log_for_clusters(path, vcenter: VCenterInfo) -> None:
    """Extract cluster display names and (where present) member hostnames."""
    tail = ""
    with path.open("rb") as f:
        while True:
            chunk = f.read(_CLUSTER_SCAN_CHUNK)
            if not chunk:
                break
            text = (tail + chunk.decode("utf-8", errors="replace"))
            tail = text[-_CHUNK_OVERLAP:]
            for match in _CLUSTER_MOREF_RE.finditer(text):
                moref = match.group("moref")
                name = match.group("name").strip()
                if name and moref not in vcenter.cluster_names:
                    vcenter.cluster_names[moref] = name
            for match in _VCLS_MEMBERSHIP_RE.finditer(text):
                moref = match.group("moref")
                rest = text[match.end(): match.end() + 65536]
                segment = rest.split("\n", 1)[0] if "\n" in rest[:65536] else rest
                members = sorted(
                    {m.group("hostname").strip().lower() for m in _HOST_MOREF_RE.finditer(segment)}
                )
                if members:
                    existing = vcenter.cluster_members.setdefault(moref, [])
                    for member in members:
                        if member not in existing:
                            existing.append(member)
