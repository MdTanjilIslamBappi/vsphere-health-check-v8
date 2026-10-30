from __future__ import annotations

from pydantic import BaseModel, Field


class VCenterApplianceDisk(BaseModel):
    """One filesystem mount on the vCenter Server appliance (from ``df``)."""

    filesystem: str
    mount: str
    size_bytes: int | None = None
    used_bytes: int | None = None
    available_bytes: int | None = None
    percent_used: int | None = None


class VCenterInfo(BaseModel):
    """Parsed, normalised data for a vCenter Server support bundle.

    A ``vc-support`` bundle is structurally different from an ESXi
    ``vm-support`` bundle: it is a mirror of the VCSA appliance filesystem
    rather than of an ESXi host. vhealth currently reads appliance-level
    health signals only -- identity/version, ``service-control`` service
    status and appliance filesystem usage. vCenter *database* content
    (EVC baselines, datastores, VM inventory, active alarms) is not
    exposed in a form this tool reads, and remains out of scope; see
    SUPPORTED_FORMATS.md.
    """

    hostname: str
    bundle_source: str
    hostname_source: str | None = None
    captured_on: str | None = None
    vm_support_version: str | None = None
    vc_version: str | None = None
    vc_build: str | None = None
    os_kernel: str | None = None
    services_running: list[str] = Field(default_factory=list)
    services_stopped: list[str] = Field(default_factory=list)
    appliance_disks: list[VCenterApplianceDisk] = Field(default_factory=list)
    # Cluster inventory evidence extracted from the current vpxd operational
    # log: moref -> display name, and moref -> member hostnames. This is
    # log-derived, not a direct read of the vCenter inventory database.
    cluster_names: dict[str, str] = Field(default_factory=dict)
    cluster_members: dict[str, list[str]] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)

    def coverage(self) -> dict[str, bool]:
        """Which appliance diagnostic categories vhealth actually found."""
        return {
            "readme": self.captured_on is not None,
            "system_version": self.vc_version is not None,
            "service_status": bool(self.services_running or self.services_stopped),
            "appliance_disk_usage": len(self.appliance_disks) > 0,
            "cluster_inventory": bool(self.cluster_names),
        }
