# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - Unreleased

Initial implementation. Built and tested on Windows 11 with Python 3.12 and
`uv` 0.13. Also tested on Linux via WSL2 (Kali Linux, Debian-based) --
install, the full test suite, a real `assess` run, and uninstall all pass
there too -- but this is not a bare-metal/Ubuntu test, and the PyInstaller
build is still Windows-only (see [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md)
and the "Known limitations" section of [README.md](README.md)).

### Changed

- Report convention rework based on direct user feedback on the first
  redesign: the main report now mirrors a customer-facing executive
  health-check convention exactly (Executive Summary, Scope, System
  Status 3.1-3.4 ending in Recommendation -- no more), written in report
  voice ("This quarterly health check assessment was performed on the
  customer's...") instead of tool/software voice. The full per-finding
  evidence dump that used to live inline in the main report now lives in
  a separate companion document instead (`findings-log.docx`/
  `findings-log.html`, written automatically alongside `report.docx`/
  `report.html`), so the main report stays a concise executive read.
- Log-based findings (PDL/APD/dead-path/ALUA/VOB) are now scoped to the
  last 90 days of the bundle's own capture date -- this is a *quarterly*
  health check, so an event from a year-old log rotation no longer
  appears as an active finding. Older matches are still tallied
  (`HostInfo.log_signal_counts_excluded`) rather than discarded, and a
  finding's limitations note how many older occurrences exist outside
  the window, but they do not drive severity or an active finding.

### Added

- New default HTML/DOCX report layout: cover page, a Version History table
  (`--revision`/`--description` options, default `V01`/"Initial copy"), a
  table of contents, Executive Summary, Scope of Health Check (a single
  checked/not-checked bullet list -- EVC mode, datastores, VM inventory,
  and vCenter alarms are listed as explicitly not assessed rather than
  guessed or silently omitted, since an ESXi host bundle has no vCenter
  data), and System Status: 3.1 an aggregate Hardware Status grid, 3.2 a
  VMware Components status table (Component/Status/Remarks) plus a "Key
  Findings at a Glance" bullet list, 3.3 an ESXi host inventory table
  (Server Name/Management IP/Server Model/CPU Model) plus a "Detailed
  Observations" bullet list, and 3.4 Recommendation grouping findings by
  rule with an Affected/Action layout. See RULE_CATALOG.md and
  SUPPORTED_FORMATS.md.
- `findings-log.docx`/`findings-log.html`: a companion document, written
  automatically alongside every `report.docx`/`report.html`, carrying the
  full per-finding detail (evidence lines, remediation, limitations) that
  used to live inline in the main report.
- `hardware_inventory.py` parser: server manufacturer/model and CPU model
  (from `commands/smbiosDump.txt`), management IP (`vmk0` from
  `commands/esxcfg-vmknic_-l.txt`), and host-reported cluster/compute-resource
  membership (`commands/clusterAdmin_cluster-status.txt`, where present).
  Validated against real EAMSC2 bundles: extracted server model, CPU
  model, and management IP matched a prior hand-written customer report
  for the same hosts exactly.
- `fleet.cpu_model_mismatch` rule: a new "fleet rule" category that
  compares data *across* every host in one assessment rather than one
  host at a time, flagging mixed CPU models (a real vMotion/EVC
  compatibility risk) across the hosts in a single run.
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

- CI's `push` trigger (`.github/workflows/ci.yml`) was scoped to
  `branches: [main]`, but the repository's actual default branch is
  `master` -- so pushing straight to `master` never ran CI via that
  trigger (the `pull_request` trigger was unaffected). Found during a
  Stage 0 baseline audit; fixed by pointing the trigger at `master`.
- `_resolve_authorship()` decided whether to prompt based solely on
  `sys.stdin.isatty()`, which can report a tty is attached even in some
  unattended/automation contexts with nobody present to answer -- leaving
  the prompt to hang indefinitely. The prompts are now wrapped so an
  `EOFError`/abort while reading input is treated the same as
  `--no-prompt` (leave the field unset) instead of propagating.
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
