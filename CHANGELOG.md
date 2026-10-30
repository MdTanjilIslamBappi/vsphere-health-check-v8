# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - Unreleased

Initial implementation. Built and tested on Windows 11 with Python 3.12 and
`uv` 0.13; **not yet tested on Linux** (see [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md)
and the "Known limitations" section of [README.md](README.md)).

### Added

- `vhealth` CLI (`inspect`, `assess`, `report`, `--version`) built on Click.
- Safe, offline extraction of `.zip` and `.tgz` support bundles with
  zip-slip protection, size/entry/compression-ratio limits, and graceful
  degradation on truncated/corrupted archives.
- Discovery of ESXi `vm-support` host bundles inside a single-host `.tgz`
  or a multi-host vCenter-style `.zip`.
- Parsers for: vm-support `README` metadata, ESXi version/build/hostname,
  storage adapter/device inventory (`esxcli storage core`), SMART health
  (`smartinfo.txt`), IPMI hardware sensors, and storage/hardware signals
  from rotated `vmkwarning`/`vobd` logs.
- A rule engine with findings for: SMART health failures and reallocated
  sectors, storage devices not in the `on` state, asserted IPMI hardware
  sensors, and PDL/APD/dead-path/ALUA/VOB storage log signals.
- Versioned, machine-readable `assessment.json` output (schema v1.0.0)
  carrying full reproducibility metadata (input hash, parser/rule-engine
  versions, evidence manifest, processing warnings).
- HTML (Jinja2) and Word (`python-docx`) report generation from either a
  fresh assessment or a saved `assessment.json`.
- `scripts/install.ps1` / `scripts/install.sh` for a reproducible,
  project-local, non-admin install via `uv`.
- Unit, integration, security and cross-platform test suites using
  synthetic fixtures (no customer data).
- `scripts/build_release.py` (PyInstaller, one-file build). Built and
  smoke-tested on Windows 11/Python 3.12: the resulting
  `vhealth-windows-amd64.exe` (~18 MB) ran `--version` and a full
  `assess` (bundled templates/config/schema included) outside the repo
  and outside the dev virtualenv. **Not yet built or tested on Linux.**

### Known limitations

- Linux has not been run or tested yet; only Windows 11 + Python 3.12 has
  been validated end-to-end.
- Only a `vmkwarning`-derived subset of vmkernel events is scanned; this
  tool does not decode the binary VLF log format some ESXi 8.x releases
  use for the full `vmkernel.log` (see SUPPORTED_FORMATS.md).
- PyInstaller build verified on Windows only; Linux portable binary not
  yet attempted.
- Offline installation package procedure validated on Windows (see
  `docs/OFFLINE_INSTALL.md`); not yet attempted on Linux. On this
  development machine, a local Windows Application Control policy
  blocked running the generated `vhealth.exe` shim directly (though
  `python -m vhealth.cli` worked); if you hit the same thing, see that
  doc's "Known gap" section.
- Rule catalogue covers storage/RAID/hardware-sensor health only; no
  networking, compute, or vSAN-specific rules yet.
