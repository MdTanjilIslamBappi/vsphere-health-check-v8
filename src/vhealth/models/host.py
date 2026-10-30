from __future__ import annotations

from pydantic import BaseModel, Field


class StorageAdapter(BaseModel):
    """A storage HBA/RAID controller (esxcli storage core adapter)."""

    device: str
    driver: str | None = None
    description: str | None = None
    link_state: str | None = None
    uid: str | None = None


class StorageDevice(BaseModel):
    """A storage device/LUN (esxcli storage core device list)."""

    device: str
    display_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    is_ssd: bool | None = None
    is_local: bool | None = None
    size_mib: int | None = None
    raid_level: str | None = None
    status: str | None = None
    multipath_plugin: str | None = None
    smart_overall_health: str | None = None
    smart_raw: dict[str, str] = Field(default_factory=dict)


class Datastore(BaseModel):
    """A VMFS datastore (vmkfstools -P -v 10 <volume>), mapped to its backing devices.

    ``naa_ids`` lets findings that only know a bare device ID (e.g. a PDL/APD
    event against ``naa.xxxx``) show the human-readable datastore name
    instead -- see ``HostInfo.datastore_for_naa``.
    """

    name: str
    uuid: str | None = None
    naa_ids: list[str] = Field(default_factory=list)


class VirtualMachine(BaseModel):
    """A powered-on VM, as reported by the host itself (localcli vm process list).

    Only VMs running *at capture time* appear here -- a support bundle has
    no record of powered-off VMs, since that inventory lives solely in
    vCenter's own database. ``datastore_uuid`` is the first path segment
    of ``config_path`` (``/vmfs/volumes/<uuid>/...``); resolve it to a
    name via ``HostInfo.datastore_name_for_uuid``.
    """

    name: str
    uuid: str | None = None
    world_id: str | None = None
    config_path: str | None = None
    datastore_uuid: str | None = None
    # True only when this VM's own vmware.log power-on record contains the
    # documented "FeatureCompat: No EVC masks." line -- real, host-independent
    # evidence that no EVC CPU-feature mask is being applied to it right now.
    # This is NOT a read of the cluster's configured EVC baseline (no bundle
    # contains that); it says nothing when False/absent, since that could
    # mean masks *are* applied, or simply that no matching log line was found.
    no_evc_masks_observed: bool = False


class HardwareSensor(BaseModel):
    """An IPMI/SDR hardware sensor reading (fan, temp, voltage, PSU)."""

    name: str
    reading: str | None = None
    unit: str | None = None
    status: str | None = None
    sensor_type: str | None = None


COVERAGE_CATEGORIES = (
    "readme",
    "system_version",
    "storage_adapters",
    "storage_devices",
    "smart_data",
    "hardware_sensors",
    "log_signals",
    "hardware_inventory",
)


class HostInfo(BaseModel):
    """Parsed, normalised data for a single ESXi host bundle."""

    hostname: str
    bundle_source: str
    esxi_version: str | None = None
    esxi_build: str | None = None
    captured_on: str | None = None
    vm_support_version: str | None = None
    storage_adapters: list[StorageAdapter] = Field(default_factory=list)
    storage_devices: list[StorageDevice] = Field(default_factory=list)
    datastores: list[Datastore] = Field(default_factory=list)
    virtual_machines: list[VirtualMachine] = Field(default_factory=list)
    vm_inventory_available: bool = False
    # NTP time-synchronization status (esxcli system ntp get). ``ntp_enabled``
    # and ``ntp_time_synchronized`` are distinct: a host can have the NTP
    # service enabled and a server configured yet never actually sync (e.g.
    # an unreachable server), which is exactly the condition worth flagging.
    ntp_data_available: bool = False
    ntp_enabled: bool | None = None
    ntp_time_synchronized: bool | None = None
    ntp_servers: list[str] = Field(default_factory=list)
    sensors: list[HardwareSensor] = Field(default_factory=list)
    log_events: list[str] = Field(default_factory=list)
    log_signal_counts: dict[str, int] = Field(default_factory=dict)
    log_signal_counts_excluded: dict[str, int] = Field(default_factory=dict)
    log_data_available: bool = False
    server_manufacturer: str | None = None
    server_model: str | None = None
    cpu_model: str | None = None
    cpu_sockets: int | None = None
    management_ip: str | None = None
    cluster_id: str | None = None
    # ``cluster_state`` is the raw clusterAdmin state string ("standalone",
    # "hosted", ...). ``cluster_name`` is resolved from the vCenter Server
    # bundle when the assessment includes one; see
    # ``vhealth.parsers.vcenter`` for how it is extracted.
    cluster_state: str | None = None
    cluster_name: str | None = None
    cluster_in_alarm: bool | None = None
    parse_warnings: list[str] = Field(default_factory=list)

    def datastore_for_naa(self, naa_id: str) -> str | None:
        """Look up the datastore name backed by a given ``naa.xxxx`` device ID."""
        naa_id = naa_id.lower()
        for ds in self.datastores:
            if naa_id in (n.lower() for n in ds.naa_ids):
                return ds.name
        return None

    def datastore_name_for_uuid(self, datastore_uuid: str | None) -> str | None:
        """Look up a datastore's name from its VMFS UUID (a VM's mount-point segment)."""
        if not datastore_uuid:
            return None
        for ds in self.datastores:
            if ds.uuid and ds.uuid.lower() == datastore_uuid.lower():
                return ds.name
        return None

    def coverage(self) -> dict[str, bool]:
        """Which diagnostic data categories vhealth actually found for this host.

        ``log_signals`` reflects whether vmkwarning/vobd rotations were found
        at all, not whether any rotation contained a matching bad signal --
        a healthy host with clean logs must show as covered, not missing.
        """
        return {
            "readme": self.captured_on is not None,
            "system_version": self.esxi_version is not None,
            "storage_adapters": len(self.storage_adapters) > 0,
            "storage_devices": len(self.storage_devices) > 0,
            "smart_data": any(d.smart_overall_health for d in self.storage_devices),
            "hardware_sensors": len(self.sensors) > 0,
            "log_signals": self.log_data_available,
            "hardware_inventory": self.server_model is not None or self.cpu_model is not None,
        }
