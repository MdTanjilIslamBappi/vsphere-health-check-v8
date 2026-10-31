# Supported formats

## Tested operating-system / Python matrix

| OS | Python | Status |
|---|---|---|
| Windows 11 Pro (build 26300) | 3.12.10 | Tested (this repository's development environment) |
| Windows 10 | 3.11+ | Not yet tested |
| Kali Linux (Debian-based), via WSL2 | 3.14.9 | Tested: install.sh, the full pytest suite, a real `assess` run against a synthetic bundle via the installed CLI binary, and uninstall.sh (including idempotent re-run and a reinstall afterward) all passed. **Not** bare-metal, **not** a container, **not** Ubuntu specifically. |
| Ubuntu LTS (bare-metal or VM) | 3.11+ | Not yet tested |
| Debian (bare-metal or VM) | 3.11+ | Not yet tested |

Only rows marked "Tested" have actually been run. Do not read the other
rows as a compatibility claim -- the code avoids known Windows/Linux
divergences (see below) and is expected to work, but "expected to work"
and "tested" are tracked separately in this table on purpose, per this
project's own rule against claiming compatibility that hasn't been
verified. WSL2 shares the real Linux kernel and userland, so this is a
genuine Linux test of the CLI/install/uninstall path -- but it is not the
same as bare-metal Ubuntu, and the PyInstaller build in
`scripts/build_release.py` has still only been built and smoke-tested on
Windows (see CHANGELOG.md).

## Input bundle formats

| Format | Support |
|---|---|
| Single ESXi host `vm-support` bundle (`.tgz`) | Supported |
| Multi-host vCenter support bundle (`.zip` containing per-host `.tgz` members) | Supported |
| Encrypted/password-protected archives | Not supported (rejected with an actionable error) |

Detection is by sniffing actual archive content (`zipfile.is_zipfile` /
`tarfile.is_tarfile`), not by file extension.

## ESXi version coverage

Validated against real (anonymised-by-omission, not committed to this
repository) ESXi 8.0.3 `vm-support` bundles. The file layout parsed here
(`README`, `commands/*`, `json/*`, `var/run/log/*`) has been stable since
ESXi 6.x, but only 8.0.3 has actually been exercised.

## What is parsed

| Source file | Parser | Notes |
|---|---|---|
| `README` | `readme.py` | Capture timestamp, vm-support version |
| `commands/uname_-a.txt`, `commands/localcli_system-version-get.txt` | `system_version.py` | Hostname, ESXi version/build |
| `json/localcli_storage-core-adapter-list.json` | `storage_core.py` | HBA/controller inventory |
| `json/localcli_storage-core-device-list.json` | `storage_core.py` | Storage device/LUN inventory |
| `commands/smartinfo.txt` | `smart.py` | SMART health for devices that expose it |
| `commands/localcli_hardware-ipmi-sdr-list--p--i--n-all.txt` | `sensors.py` | IPMI hardware sensors (fan/temp/voltage/PSU) |
| `var/run/log/vmkwarning.{0..7}.gz` | `vmk_log.py` | PDL/APD/dead-path/ALUA warning signals |
| `var/run/log/vobd.{0..7}.gz` | `vmk_log.py` | `esx.problem.*` VOB events |
| `commands/smbiosDump.txt` | `hardware_inventory.py` | Server manufacturer/model, CPU model, CPU socket count |
| `commands/esxcfg-vmknic_-l.txt` | `hardware_inventory.py` | Management IP (the `vmk0` VMkernel NIC, by convention -- see below) |
| `commands/clusterAdmin_cluster-status.txt` | `hardware_inventory.py` | Host-reported cluster/compute-resource ID and local alarm state, where the file is present |
| `commands/localcli_--formatterjson-system-ntp-get.txt` | `ntp.py` | NTP enabled/configured-server state and, separately, whether the host's clock is actually synchronized right now |
| `commands/localcli_system-coredump-file-list.txt` | `coredump.py` | Whether a file-based kernel-coredump target is both active and configured |
| `commands/localcli_software-vib-list.txt` | `vib.py` | Installed VIB acceptance levels; flags any `CommunitySupported` (unsupported by VMware GSS) VIB |
| `commands/localcli_storage-nmp-path-list.txt` | `multipath.py` | Per-device multipath path state (active/active unoptimized/dead), aggregated across every path block naming that device |
| `commands/esxcfg-vswitch_-l.txt` | `vswitch.py` | Standard vSwitch/DVS name, MTU, used-port count, and uplink NIC list |
| `commands/localcli_hardware-ipmi-sel-list--p--i--n-all.txt` | `ipmi_sel.py` | IPMI System Event Log history: uncorrectable-ECC, drive predictive-failure, PSU-failure, and critical-temperature `Assert` signals |
| `commands/nicinfo.sh.txt` | `nic_link.py` | Physical NIC link state (Up/Down), cross-referenced against vSwitch/DVS uplink lists |
| `commands/vmkfstools_-P--v-10-vmfsvolumes*.txt` | `datastore.py` | VMFS datastore name/UUID, backing device IDs, and point-in-time capacity/free-space (deduplicated fleet-wide by `fleet.datastore_usage_warning`/`_critical` in `fleet_rules.py`) |
| `commands/sqlite3_etcvmwareconfigstorecurrent-store-1-PRAGMAintegrity_check.txt` | `configstore.py` | ESXi's host-configuration database (ConfigStore) SQLite integrity check result (`ok` vs. a corruption description) |
| `commands/mobility_network_health_check.txt` | `mobility.py` | ESXi's own built-in migration-network (vMotion/Provisioning) health-check verdict and sub-check detail (JSON; a Python traceback instead of JSON on some builds means the tool itself failed to run) |
| `commands/localcli_software-profile-get---rebooting-image.txt` | `pending_reboot.py` | Whether an image profile is staged but not yet applied by a reboot (vs. the literal "No pending image profile available.") |
| `var/lib/vmware/osdata/healthd/vmw.memoryHealth-*.json` | `memory_health.py` | ESXi's own built-in memory-health verdict: physical/ECC hardware state (plus corrected/uncorrected error counts since boot) and memory-reservation admission-control state, from whichever rotated snapshot has the most recent timestamp |
| `var/lib/vmware/osdata/healthd/vmw.nfsDatastoreHealth-*.json` | `nfs_datastore_health.py` | ESXi's own built-in per-NFS-datastore accessibility/mount verdict, from whichever rotated snapshot has the most recent timestamp; an empty list means no NFS datastore is configured on that host |

## Known gaps (not yet implemented)

- **Binary VLF logs.** Some ESXi 8.x configurations store the full
  `vmkernel.log`/`hostd.log` in VMware's binary VLF format under
  `var/log/vlf/` instead of (or in addition to) plain text. This tool
  does not decode VLF; it relies on `vmkwarning`/`vobd`, which are
  reliably plain text, for log-based signals. A bundle with only VLF logs
  and no `vmkwarning` rotations will show `log_signals: false` in
  `supported_format_coverage` rather than silently producing wrong
  results.
- **Text-only `localcli` output.** If a bundle predates the `json/`
  mirror of `localcli` command output (pre-ESXi 7, approximately), the
  storage adapter/device parsers currently report missing evidence rather
  than falling back to parsing the text tables.
- **Hardware RAID controller management tools** (`storcli`, `megacli`,
  `hpssacli`/`ssacli`) are not parsed; this tool reads what `vm-support`
  captures via `esxcli`/IPMI, not vendor-specific RAID CLI output, which
  `vm-support` does not run by default.
- **vCenter support bundle (the `vc-` member).** The vCenter appliance's
  own identity, version, `service-control` service status, and appliance
  filesystem usage are parsed (`parsers/vcenter.py`), as is cluster
  name/moref and vCLS-membership data recovered from `vpxd`'s current
  operational log. What is *not*, and cannot be, parsed from any support
  bundle (host or vCenter) is anything that lives only in vCenter's own
  inventory database: the EVC baseline *name*, vCenter-side storage-policy
  compliance status, full VM inventory (including powered-off VMs) and
  resource-utilization history, and vCenter-level active alarms.
  vCenter's `vc-support.sh` does not export that database -- confirmed by
  inspecting a real bundle's `storage/db/vpostgres/` directory, which
  contains only Postgres config files, no data. The report's "Scope of
  Health Check" section spells out this distinction per item. Datastore
  *capacity/free-space* is not on this list -- see below.
- **Running VM identity, datastore names, and datastore capacity are
  host-reported, not vCenter-reported.** `vm_inventory.py` reads each
  ESXi host's own `localcli vm process list` output (which VMs that
  host is *currently running*), and `datastore.py` reads each host's
  own `vmkfstools -P -v 10` dumps (datastore name/UUID and the same
  dump's own `Capacity .../avail` line, used by
  `fleet.datastore_usage_warning`/`fleet.datastore_usage_critical`).
  Both work from an ESXi host bundle alone, with no vCenter member
  required, and both have real gaps: a powered-off VM, or one with no
  running world at capture time, will not appear; a VMFS volume mounted
  only via its UUID symlink with no friendly-name symlink captured will
  not have a name to resolve to; and the capacity/free-space figure is a
  point-in-time snapshot at capture, not vCenter's historical trending
  graph. The
  `clusterAdmin_cluster-status.txt` cluster ID parsed by
  `hardware_inventory.py` is likewise a host-reported fact (which compute
  resource this host currently thinks it belongs to), not a read of
  vCenter's actual cluster/HA configuration.
- **EVC masking evidence comes from each running VM's own power-on log,
  not from vCenter.** `vm_inventory.py` also checks each discovered VM's
  `vmware.log`/rotation files (found alongside its `.vmx`, under
  `vmfs/volumes/<datastore>/<vm-name>/`) for the real, documented vmx
  log line `FeatureCompat: No EVC masks.`, written at every power-on.
  Finding it is genuine evidence that no EVC CPU-feature mask is applied
  to that VM right now -- but it is *not* a read of the cluster's
  configured EVC baseline name, and its absence is never treated as
  evidence that a mask *is* applied (the line could simply be outside
  the portion of the log read, or the retained rotation could predate
  the current boot). This tool has found no documented or observed log
  line for the "mask applied" case to parse with any confidence, so it
  only ever reports the negative (no masking observed), never a
  baseline name.
- **Management IP selection** in `hardware_inventory.py` assumes `vmk0` is
  the management VMkernel NIC, which is the common ESXi convention but not
  a guarantee -- a host reconfigured to manage over a different vmknic
  will show the wrong IP (or none, if `vmk0` doesn't exist).

## Windows-specific behaviour

Real vm-support bundles can contain per-VM diagnostic dump filenames
nested under `vmfs/volumes/<datastore>/<vm-name>/...` deep enough to
exceed Windows' 260-character `MAX_PATH`. Rather than universally opting
into the `\\?\` extended-path syntax (which creates a separate class of
bugs with tools like `shutil.rmtree` that don't apply that prefix
themselves), affected members are skipped with an explicit warning in
`assessment.json`'s `processing_warnings`. None of this tool's parsers
read anything under `vmfs/volumes/`, so this never causes silent loss of
evidence that a rule depends on -- but it is also not silent: it always
shows up as a warning.
