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


class VCenterCertificate(BaseModel):
    """One SSO/STS signing certificate (or its issuing CA) found in

    ``sts-certificates.txt`` (vmdir's LDAP export of the vsphere.local SSO
    domain's ``TenantCredential``/``TrustedCertificateChains`` entries).
    Deduplicated by ``serial_number`` -- per VMware's documented SSO
    architecture, the same certificate commonly appears under both its
    ``TenantCredential-N`` (currently used to sign tokens) and
    ``TrustedCertChain-N`` (trusted to validate tokens) entries;
    ``entry_names`` lists every LDAP entry it was found under.

    This covers only the vsphere.local SSO signing certificates stored in
    vmdir -- NOT the VECS-managed Machine SSL certificate, solution-user
    certificates, or other VECS stores, since no ``vc-support`` bundle
    captures a ``vecs-cli`` dump.
    """

    serial_number: str
    subject_cn: str | None = None
    issuer_cn: str | None = None
    not_before: str | None = None
    not_after: str | None = None
    entry_names: list[str] = Field(default_factory=list)


class VCenterInfo(BaseModel):
    """Parsed, normalised data for a vCenter Server support bundle.

    A ``vc-support`` bundle is structurally different from an ESXi
    ``vm-support`` bundle: it is a mirror of the VCSA appliance filesystem
    rather than of an ESXi host. vhealth currently reads appliance-level
    health signals only -- identity/version, ``service-control`` service
    status, appliance filesystem usage, and SSO/STS certificate expiry.
    vCenter *database* content (EVC baselines, datastores, VM inventory,
    active alarms) is not exposed in a form this tool reads, and remains
    out of scope; see SUPPORTED_FORMATS.md.
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
    # SSO/STS signing certificate expiry (sts-certificates.txt). See
    # VCenterCertificate's docstring for exactly what this does and does
    # not cover.
    sts_certificates_data_available: bool = False
    sts_certificates: list[VCenterCertificate] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)

    def coverage(self) -> dict[str, bool]:
        """Which appliance diagnostic categories vhealth actually found."""
        return {
            "readme": self.captured_on is not None,
            "system_version": self.vc_version is not None,
            "service_status": bool(self.services_running or self.services_stopped),
            "appliance_disk_usage": len(self.appliance_disks) > 0,
            "cluster_inventory": bool(self.cluster_names),
            "sts_certificates": self.sts_certificates_data_available,
        }
