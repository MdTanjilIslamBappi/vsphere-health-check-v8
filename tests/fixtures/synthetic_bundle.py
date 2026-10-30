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

_SMBIOS_DUMP = """Dumping live SMBIOS data!
SMBIOS version 3.2
  System Info (Type 1): #256
    Manufacturer: "{server_manufacturer}"
    Product: "{server_model}"
    Serial: "SYN0001"
  Processor Info (Type 4): #1024
    Socket: "CPU1"
    Socket Status: Populated, Enabled
    Manufacturer: "{cpu_manufacturer}"
    Version: "{cpu_model}"
  Processor Info (Type 4): #1025
    Socket: "CPU2"
    Socket Status: Populated, Enabled
    Manufacturer: "{cpu_manufacturer}"
    Version: "{cpu_model}"
"""

_VMKNIC_LIST = """Interface  Port Group/DVPort/Opaque Network        IP Family IP Address                              Netmask         Broadcast       MAC Address       MTU     TSO MSS   Enabled Type                NetStack
vmk0       9                                       IPv4      {management_ip}                           255.255.255.0   {management_ip}  00:50:56:00:00:01 1500    65535     true    STATIC              defaultTcpipStack
"""

_CLUSTER_STATUS = """{{
   "state": "hosted",
   "cluster_id": "{cluster_id}",
   "is_in_alarm": {in_alarm},
   "is_in_cluster": true
}}
"""


def build_host_dir(
    root: Path,
    hostname: str = "esxi-synthetic-01.example.test",
    smart_health: str = "OK",
    sensor_asserted: bool = False,
    include_pdl_warning: bool = False,
    include_old_pdl_warning: bool = False,
    minimal_capture: bool = False,
    server_manufacturer: str = "Synthetic Inc.",
    server_model: str = "SynthServer R1",
    cpu_manufacturer: str = "Intel",
    cpu_model: str = "Intel(R) Xeon(R) Gold 6258R CPU @ 2.70GHz",
    management_ip: str = "192.168.100.10",
    cluster_id: str = "cluster-synthetic-01",
    cluster_in_alarm: bool = False,
    datastore_name: str | None = None,
) -> Path:
    """Create a synthetic vm-support host directory tree under ``root``.

    ``minimal_capture=True`` mimics a reduced/incident-mode vm-support run
    (observed in real EAMSC2 bundles): only README and system-version are
    present, with no storage-core, SMART, IPMI, or log data at all.

    ``datastore_name``, if given, adds a ``vmkfstools -P -v 10`` dump for a
    VMFS datastore backed by the synthetic SAN disk
    (``naa.6000000000000000000000000000001``), so a rule's output can be
    checked for the resolved datastore name instead of the bare device ID.
    """
    bundle_dir = root / f"esx-{hostname}-2026-01-15"
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
    if include_old_pdl_warning:
        # Captured on 2026-01-15; this is ~1 year earlier, well outside the 90-day
        # quarterly log window -- it should be tallied as excluded, not as a finding.
        vmkwarning_lines.append(
            "2025-01-10T10:05:00.000Z Wa(180) vmkwarning: cpu0:1)WARNING: NMP: "
            "nmp_PathDetermineFailure:3536: Cmd (0x1a) PDL error (0x5/0x25/0x0) - "
            "path vmhba2:C0:T0:L1 device naa.6000000000000000000000000000002\n"
        )
    with gzip.open(bundle_dir / "var" / "run" / "log" / "vmkwarning.0.gz", "wb") as f:
        f.write("".join(vmkwarning_lines).encode("utf-8"))
    with gzip.open(bundle_dir / "var" / "run" / "log" / "vobd.0.gz", "wb") as f:
        f.write(b"2026-01-15T10:00:00.000Z In(14) vobd[1]:  routine startup message\n")

    (bundle_dir / "commands" / "smbiosDump.txt").write_text(
        _SMBIOS_DUMP.format(
            server_manufacturer=server_manufacturer,
            server_model=server_model,
            cpu_manufacturer=cpu_manufacturer,
            cpu_model=cpu_model,
        ),
        encoding="utf-8",
    )
    (bundle_dir / "commands" / "esxcfg-vmknic_-l.txt").write_text(
        _VMKNIC_LIST.format(management_ip=management_ip), encoding="utf-8"
    )
    (bundle_dir / "commands" / "clusterAdmin_cluster-status.txt").write_text(
        _CLUSTER_STATUS.format(
            cluster_id=cluster_id, in_alarm="true" if cluster_in_alarm else "false"
        ),
        encoding="utf-8",
    )

    if datastore_name is not None:
        vmkfstools_dump = (
            "VMFS-6.82 (Raw Major Version: 24) file system spanning 1 partitions.\n"
            f"File system label (if any): {datastore_name}\n"
            "Mode: public ATS-only\n"
            "UUID: 6000000-0000000-0000-000000000001\n"
            "Partitions spanned (on \"lvm\"):\n"
            "\tnaa.6000000000000000000000000000001:1\n"
        )
        (
            bundle_dir
            / "commands"
            / f"vmkfstools_-P--v-10-vmfsvolumes{datastore_name}.txt"
        ).write_text(vmkfstools_dump, encoding="utf-8")

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


# --- vCenter Server (vc-support) bundle fixtures ---------------------------

_VCSA_README = """Command line: vc-support /bin/vc-support -q -w /etc/vmware-vpx/bundle-stage
Bundle name: None
Captured on: 2026-01-15 11:00:00.000000
vm-support version: v4.1

Files/Directories of Interest:
------------------------------
commands: a directory containing output files for all commands run
"""

_VCSA_UNAME = "Linux vcsa.example.test 5.10.0-1.ph4 #1-photon SMP x86_64 GNU/Linux\n"

_VCSA_RPM = """VMware-vpxd-8.0.3.00900-12345678.x86_64
VMware-vpxd-agents-eesx-8.0.3.00900-12345678.x86_64
vsphere-ui-8.0.3.00900-12345678.noarch
openssh-server-8.9-1.ph4.x86_64
"""

_VCSA_SERVICES = """Running:
 applmgmt lookupsvc vmdird vmware-vpxd vmware-vpostgres vmware-rhttpproxy
Stopped:
 vmcam vmonapi vmware-imagebuilder vmware-vcha
"""

_VCSA_DF = """Filesystem                               1K-blocks     Used Available Use% Mounted on
devtmpfs                                      4096        0      4096   0% /dev
/dev/mapper/vg_root_0-lv_root_0           49222292 16738388  29951144  36% /
/dev/mapper/db_vg-db                      25618660 23056794   20601068  92% /storage/db
/dev/mapper/archive_vg-archive           102618040 92358504   5000684  95% /storage/archive
tmpfs                                         1024        0      1024   1% /var/spool/snmp
"""

_VPXD_LOG = """2026-01-15T07:44:43.913Z info vpxd[07159] [Originator@6876 sub=MoCluster opID=CSMM-domain-c1001-168231] Dispatching cluster store membership request; {00007fee8c005300, HEALTH, domain-c1001, (null), attempt: 168107}
2026-01-15T07:44:58.322Z info vpxd[07176] [Originator@6876 sub=cdrsPlmt opID=CdrsLoadBalancer-90f017f] Dump section 10260733345838 created for cluster [vim.ClusterComputeResource:domain-c1001,EAMSC2]
"""

# Membership lines carry the member host morefs on the same line; each
# ``[vim.HostSystem:host-N,HOSTNAME]`` chunk is one member.
_VCLS_MEMBERSHIP_LINE = (
    "2026-01-15T07:44:20.148Z info vpxd[2422740] [Originator@6876 sub=MoCluster "
    "opID=PodCrxMgr-domain-c1001-174317] Dumping vCLS Pod Crx host infos; domain-c1001, "
    "[{[vim.HostSystem:host-13043,esx01-synthetic.example.test], st: 0, vm: (null), t: "
    "}, {[vim.HostSystem:host-13044,esx02-synthetic.example.test], st: 0, vm: (null)}"
    ", attempt: 174317}\n"
)


def build_vcsa_dir(
    root: Path,
    cluster_name: str = "EAMSC2",
    cluster_moref: str = "domain-c1001",
    vcls_membership: bool = True,
) -> Path:
    """Create a synthetic vc-support appliance bundle directory under ``root``.

    Directory names are deliberately kept short: the extraction guard
    skips paths longer than Windows' safe-MAX_PATH (240 chars), so long
    fixture names would silently produce an empty bundle under the
    pytest tmp_path prefix.
    """
    dir_name = "vc-vcsa.example.test"
    bundle_dir = root / dir_name
    (bundle_dir / "commands").mkdir(parents=True)
    (bundle_dir / "var" / "log" / "vmware" / "vpxd").mkdir(parents=True)

    (bundle_dir / "README").write_text(_VCSA_README, encoding="utf-8")
    (bundle_dir / "commands" / "uname_-a.txt").write_text(_VCSA_UNAME, encoding="utf-8")
    (bundle_dir / "commands" / "rpm_-qa.txt").write_text(_VCSA_RPM, encoding="utf-8")
    (bundle_dir / "commands" / "service-control_--status---all.txt").write_text(
        _VCSA_SERVICES, encoding="utf-8"
    )
    (bundle_dir / "commands" / "df.txt").write_text(_VCSA_DF, encoding="utf-8")

    log_text = _VPXD_LOG.replace("domain-c1001", cluster_moref).replace("EAMSC2", cluster_name)
    if vcls_membership:
        log_text += _VCLS_MEMBERSHIP_LINE.replace("domain-c1001", cluster_moref)
    (bundle_dir / "var" / "log" / "vmware" / "vpxd" / "vpxd-2508.log").write_text(
        log_text, encoding="utf-8"
    )
    return bundle_dir


def build_vcenter_bundle_tgz(output_path: Path, **vcsa_kwargs) -> Path:
    """Build a synthetic vCenter appliance bundle as a .tgz file."""
    staging = output_path.parent / f"_staging_{output_path.stem}"
    staging.mkdir(parents=True, exist_ok=True)
    bundle_dir = build_vcsa_dir(staging, **vcsa_kwargs)

    with tarfile.open(output_path, "w:gz") as tf:
        tf.add(bundle_dir, arcname=bundle_dir.name)
    return output_path


def build_vcenter_zip_with_vcsa(
    output_path: Path, hostnames: list[str], host_cluster_id: str | None = None, **vcsa_kwargs
) -> Path:
    """Build a ZIP with per-host .tgz members plus one vCenter .tgz member.

    ``host_cluster_id`` is passed to each host bundle's clusterAdmin
    cluster-status output (defaults to the synthetic host fixture's own
    value).
    """
    staging = output_path.parent / f"_staging_{output_path.stem}"
    staging.mkdir(parents=True, exist_ok=True)

    vcsa_tgz = staging / "vcsa.tgz"
    build_vcenter_bundle_tgz(vcsa_tgz, **vcsa_kwargs)

    with zipfile.ZipFile(output_path, "w") as zf:
        zf.write(vcsa_tgz, arcname=vcsa_tgz.name)
        for hostname in hostnames:
            tgz_path = staging / f"{hostname}.tgz"
            if host_cluster_id is not None:
                build_tgz(tgz_path, hostname=hostname, cluster_id=host_cluster_id)
            else:
                build_tgz(tgz_path, hostname=hostname)
            zf.write(tgz_path, arcname=tgz_path.name)
    return output_path
