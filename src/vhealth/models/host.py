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
    parse_warnings: list[str] = Field(default_factory=list)
