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
    cluster_in_alarm: bool | None = None
    parse_warnings: list[str] = Field(default_factory=list)

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
