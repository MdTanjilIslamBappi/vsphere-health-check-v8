"""Builds a small, synthetic ESXi vm-support bundle for tests.

Nothing here is derived from a real customer bundle; the file layout and
command names are the publicly documented vm-support structure, and all
values (hostnames, device IDs, log lines) are made up.
"""

from __future__ import annotations

import gzip
import json
import tarfile
import zipfile
from pathlib import Path

_README = """Command line: vm-support.cgi /usr/lib/vmware/hostd/cgi-bin/vm-support.cgi
Bundle name: None
Captured on: 2026-01-15 10:00:00.000000
vm-support version: v4.1

Files/Directories of Interest:
------------------------------
commands: a directory containing output files for all commands run
"""

_SYSTEM_VERSION = """VersionGet:
   Product: VMware ESXi
   Version: 8.0.3
   Build: Releasebuild-99999999
   Update: 3
   Patch: 100
"""

_UNAME = "VMkernel {hostname} 8.0.3 #1 SMP Release build-99999999 Jan 1 2026 00:00:00 x86_64 x86_64 x86_64 ESXi\n"

_SDR_LIST = """Node-Sensor  Description                        Entity-Instance  Computed Reading   Base Unit            Raw Reading  Sensor Type                  Timestamp/Comment    Raw  Formatted-Raw
-----------  ---------------------------------  ---------------  -----------------  -------------------  -----------  ---------------------------  -------------------  ---  -------------
0.1          System Fan 1                       7.1              2000 RPM           RPM                  1            Fan                          2026-01-15T10:00:00       01   01
0.2          PS1 PG FAIL                        7.1              {ps1_state}        assert-discrete      1            Power Supply                 2026-01-15T10:00:00       02   02
"""


def build_host_dir(
    root: Path,
    hostname: str = "esxi-synthetic-01.example.test",
    smart_health: str = "OK",
    sensor_asserted: bool = False,
    include_pdl_warning: bool = False,
    minimal_capture: bool = False,
) -> Path:
    """Create a synthetic vm-support host directory tree under ``root``.

    ``minimal_capture=True`` mimics a reduced/incident-mode vm-support run
    (observed in real EAMSC2 bundles): only README and system-version are
    present, with no storage-core, SMART, IPMI, or log data at all.
    """
    bundle_dir = root / f"esx-{hostname}-2026-01-15--10.00-9999999"
    (bundle_dir / "commands").mkdir(parents=True)
    (bundle_dir / "json").mkdir()

    (bundle_dir / "README").write_text(_README, encoding="utf-8")
    (bundle_dir / "commands" / "localcli_system-version-get.txt").write_text(
        _SYSTEM_VERSION, encoding="utf-8"
    )
    (bundle_dir / "commands" / "uname_-a.txt").write_text(
        _UNAME.format(hostname=hostname), encoding="utf-8"
    )

    if minimal_capture:
        return bundle_dir

    (bundle_dir / "var" / "run" / "log").mkdir(parents=True)

    adapters = [
        {
            "Capabilities": [],
            "Description": "(0000:3b:00.0) Synthetic Fibre Channel Adapter",
            "Driver": "lpfc",
            "HBA Name": "vmhba2",
            "Link State": "link-up",
            "UID": "fc.synthetic:0",
        }
    ]
    (bundle_dir / "json" / "localcli_storage-core-adapter-list.json").write_text(
        json.dumps(adapters), encoding="utf-8"
    )

    devices = [
        {
            "Device": "naa.6000000000000000000000000000001",
            "Display Name": "Synthetic SAN Disk",
            "Vendor": "SYN",
            "Model": "SynthDisk",
            "Is SSD": True,
            "Is Local": False,
            "Size": 1048576,
            "RAID Level": "unknown",
            "Status": "on",
            "Multipath Plugin": "NMP",
        },
        {
            "Device": "t10.synthetic_local_nvme",
            "Display Name": "Synthetic Local NVMe",
            "Vendor": "SYN",
            "Model": "SynthNVMe",
            "Is SSD": True,
            "Is Local": True,
            "Size": 524288,
            "RAID Level": "unknown",
            "Status": "on",
            "Multipath Plugin": "NMP",
        },
    ]
    (bundle_dir / "json" / "localcli_storage-core-device-list.json").write_text(
        json.dumps(devices), encoding="utf-8"
    )

    smartinfo = (
        "Failed to get SMART stats for naa.6000000000000000000000000000001 error Cannot open device \n"
        "------------------------------------------------------------ \n\n"
        "SMART Data for Disk : t10.synthetic_local_nvme\n"
        "Parameter                       Value  Threshold Worst  Raw\n"
        "----------------------------------------------------------- \n"
        f"Health Status           \t {smart_health}\t N/A\t N/A\t N/A\n"
        "Reallocated Sector Count\t 0\t 90\t N/A\t N/A\n"
        "Drive Temperature       \t 30\t N/A\t N/A\t N/A\n"
        "------------------------------------------------------------ \n"
    )
    (bundle_dir / "commands" / "smartinfo.txt").write_text(smartinfo, encoding="utf-8")

    ps1_state = "State Asserted  " if sensor_asserted else "State Deasserted"
    (bundle_dir / "commands" / "localcli_hardware-ipmi-sdr-list--p--i--n-all.txt").write_text(
        _SDR_LIST.format(ps1_state=ps1_state), encoding="utf-8"
    )

    vmkwarning_lines = [
        "2026-01-15T10:00:00.000Z Wa(180) vmkwarning: cpu0:1)WARNING: routine startup message\n"
    ]
    if include_pdl_warning:
        vmkwarning_lines.append(
            "2026-01-15T10:05:00.000Z Wa(180) vmkwarning: cpu0:1)WARNING: NMP: "
            "nmp_PathDetermineFailure:3536: Cmd (0x1a) PDL error (0x5/0x25/0x0) - "
            "path vmhba2:C0:T0:L0 device naa.6000000000000000000000000000001\n"
        )
    with gzip.open(bundle_dir / "var" / "run" / "log" / "vmkwarning.0.gz", "wb") as f:
        f.write("".join(vmkwarning_lines).encode("utf-8"))
    with gzip.open(bundle_dir / "var" / "run" / "log" / "vobd.0.gz", "wb") as f:
        f.write(b"2026-01-15T10:00:00.000Z In(14) vobd[1]:  routine startup message\n")

    return bundle_dir


def build_tgz(output_path: Path, **host_kwargs) -> Path:
    """Build a synthetic single-host ESXi bundle as a .tgz file."""
    staging = output_path.parent / f"_staging_{output_path.stem}"
    staging.mkdir(parents=True, exist_ok=True)
    bundle_dir = build_host_dir(staging, **host_kwargs)

    with tarfile.open(output_path, "w:gz") as tf:
        tf.add(bundle_dir, arcname=bundle_dir.name)
    return output_path


def build_vcenter_zip(output_path: Path, hostnames: list[str]) -> Path:
    """Build a synthetic vCenter-style bundle: a ZIP containing per-host .tgz members."""
    staging = output_path.parent / f"_staging_{output_path.stem}"
    staging.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w") as zf:
        for hostname in hostnames:
            tgz_path = staging / f"{hostname}.tgz"
            build_tgz(tgz_path, hostname=hostname)
            zf.write(tgz_path, arcname=tgz_path.name)
    return output_path
