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
- **vCenter-side data** (vSAN health, cluster/HA config, vpxd logs) in a
  vCenter support bundle is not parsed; only the per-host ESXi `vm-support`
  members inside it are.

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
