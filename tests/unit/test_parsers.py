from pathlib import Path

from synthetic_bundle import build_host_dir

from vhealth.models.host import HostInfo
from vhealth.parsers import readme, sensors, smart, storage_core, system_version, vmk_log


def _build_host(tmp_path, **kwargs) -> tuple[Path, HostInfo]:
    host_dir = build_host_dir(tmp_path, **kwargs)
    host = HostInfo(hostname="placeholder", bundle_source=str(host_dir))
    return host_dir, host


def test_readme_parser_extracts_capture_metadata(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = readme.parse(host_dir, host)
    assert warnings == []
    assert host.captured_on == "2026-01-15 10:00:00.000000"
    assert host.vm_support_version == "v4.1"


def test_system_version_parser_extracts_version_and_hostname(tmp_path):
    host_dir, host = _build_host(tmp_path, hostname="my-host.example.test")
    warnings = system_version.parse(host_dir, host)
    assert warnings == []
    assert host.esxi_version == "8.0.3 Update 3"
    assert host.esxi_build == "Releasebuild-99999999"
    assert host.hostname == "my-host.example.test"


def test_storage_core_parser_extracts_adapters_and_devices(tmp_path):
    host_dir, host = _build_host(tmp_path)
    warnings = storage_core.parse(host_dir, host)
    assert warnings == []
    assert len(host.storage_adapters) == 1
    assert host.storage_adapters[0].device == "vmhba2"
    assert len(host.storage_devices) == 2
    local = [d for d in host.storage_devices if d.is_local]
    assert local and local[0].device == "t10.synthetic_local_nvme"


def test_smart_parser_attaches_health_to_matching_device(tmp_path):
    host_dir, host = _build_host(tmp_path, smart_health="FAILED")
    storage_core.parse(host_dir, host)
    warnings = smart.parse(host_dir, host)
    assert warnings == []
    nvme = next(d for d in host.storage_devices if d.device == "t10.synthetic_local_nvme")
    assert nvme.smart_overall_health == "FAILED"
    assert nvme.smart_raw["Reallocated Sector Count"] == "0"


def test_sensors_parser_classifies_asserted_state(tmp_path):
    host_dir, host = _build_host(tmp_path, sensor_asserted=True)
    warnings = sensors.parse(host_dir, host)
    assert warnings == []
    ps1 = next(s for s in host.sensors if "PS1" in s.name)
    assert ps1.status == "asserted"


def test_sensors_parser_classifies_deasserted_state(tmp_path):
    host_dir, host = _build_host(tmp_path, sensor_asserted=False)
    sensors.parse(host_dir, host)
    ps1 = next(s for s in host.sensors if "PS1" in s.name)
    assert ps1.status == "deasserted"


def test_vmk_log_parser_counts_pdl_signal(tmp_path):
    host_dir, host = _build_host(tmp_path, include_pdl_warning=True)
    warnings = vmk_log.parse(host_dir, host)
    assert warnings == []
    assert host.log_signal_counts.get("pdl_error", 0) == 1
    assert any("pdl_error" in e for e in host.log_events)


def test_vmk_log_parser_no_pdl_signal_when_absent(tmp_path):
    host_dir, host = _build_host(tmp_path, include_pdl_warning=False)
    vmk_log.parse(host_dir, host)
    assert host.log_signal_counts.get("pdl_error", 0) == 0


def test_parsers_report_warnings_when_evidence_missing(tmp_path):
    empty_dir = tmp_path / "empty-host"
    empty_dir.mkdir()
    host = HostInfo(hostname="x", bundle_source=str(empty_dir))
    assert readme.parse(empty_dir, host) != []
    assert system_version.parse(empty_dir, host) != []
    assert storage_core.parse(empty_dir, host) != []
    assert smart.parse(empty_dir, host) != []
    assert sensors.parse(empty_dir, host) != []
    assert vmk_log.parse(empty_dir, host) != []
