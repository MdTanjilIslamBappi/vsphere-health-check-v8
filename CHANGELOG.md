# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - Unreleased

Initial implementation. Built and tested on Windows 11 with Python 3.12 and
`uv` 0.13. Also tested on Linux via WSL2 (Kali Linux, Debian-based) --
install, the full test suite, a real `assess` run, and uninstall all pass
there too -- but this is not a bare-metal/Ubuntu test, and the PyInstaller
build is still Windows-only (see [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md)
and the "Known limitations" section of [README.md](README.md)).

### Added

- `--engineer`/`--author`/`--verifier` options on `assess` and `report`,
  shown on the cover page of both the HTML and DOCX reports. Any left
  unset are prompted for interactively (press Enter to skip); `--no-prompt`
  or a non-interactive run (CI, a script) leaves them unset instead of
  hanging on a prompt. Not stored in `assessment.json` -- a report can be
  re-rendered later (e.g. a verifier adding their name) without re-running
  the assessment.
- `coverage.limited_diagnostic_data` rule: raises a visible finding (not
  just a buried metadata flag) when a bundle is missing whole categories
  of diagnostic data (storage-core, SMART, IPMI, or log signals), so a
  short findings list can't be misread as "all checked, all clean" when
  it may really mean "mostly unchecked". See RULE_CATALOG.md.
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
- `scripts/windows/uninstall.ps1` / `scripts/linux/uninstall.sh`, removing
  everything the matching install script created (the project-local
  `.venv` and local build/test caches), and a
  [Beginner's Guide](docs/BEGINNER_GUIDE.md) for readers new to the
  command line, Python tooling, or VMware terminology.
- `scripts/windows/install.ps1` / `scripts/linux/install.sh` for a
  reproducible, project-local, non-admin install via `uv`. Split into
  per-OS folders so each platform only sees its own two scripts.
- Unit, integration, security and cross-platform test suites using
  synthetic fixtures (no customer data).
- `scripts/build_release.py` (PyInstaller, one-file build). Built and
  smoke-tested on Windows 11/Python 3.12: the resulting
  `vhealth-windows-amd64.exe` (~18 MB) ran `--version` and a full
  `assess` (bundled templates/config/schema included) outside the repo
  and outside the dev virtualenv. **Not yet built or tested on Linux.**

### Fixed

- `supported_format_coverage.log_signals` (and the new coverage rule built
  on the same data) previously computed "did a bad signal fire in the
  logs" rather than "was log data present to check" -- a perfectly
  healthy host with clean vmkwarning/vobd logs was wrongly reported as
  having no log coverage at all. Found while validating against real
  data; fixed by tracking whether log rotations were found, independent
  of whether anything in them matched a known-bad pattern.

### Validated

- Re-ran the full tool against all 12 real EAMSC2 ESXi 8.0.3 `vm-support`
  bundles (locally, never committed -- see CONTRIBUTING.md). All 12
  completed without error; 11 had full diagnostic data and raised real
  storage findings (PDL, ALUA, VOB, a dead-state device); one
  (`eamsc2esxi01`) turned out to be a reduced/incident-mode capture
  missing storage-core/SMART/log data entirely, which is what led to the
  `coverage.limited_diagnostic_data` rule and the `log_signals` fix above.

### Known limitations

- Linux validation so far is limited to WSL2 (Kali Linux, Debian-based):
  install.sh/uninstall.sh, the full test suite, and a real `assess` run
  via the installed CLI binary all pass there. Bare-metal Ubuntu/Debian
  has not been tried, and the PyInstaller portable binary has still only
  been built and tested on Windows 11 + Python 3.12 (see
  [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md) for the exact matrix).
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
