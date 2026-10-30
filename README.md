# vhealth

Offline health assessment for VMware vSphere support bundles.

`vhealth` reads a customer-supplied ESXi/vCenter diagnostic bundle (the
`.zip`/`.tgz` produced by `vm-support`), runs a catalogue of assessment
rules against it, and produces a professional HTML/DOCX report — entirely
on your own machine. It never connects to vCenter, an ESXi host, or any
external/cloud service, and it never requires customer credentials.

## Status

Early alpha. See [CHANGELOG.md](CHANGELOG.md) for what has actually been
built and tested so far, and [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md)
for which bundle formats and ESXi versions have been validated.

New to this, or new to the command line / VMware in general? Start with
the [Beginner's Guide](docs/BEGINNER_GUIDE.md) instead — it walks through
every step in plain English.

## Requirements

* Python 3.11+
* [uv](https://docs.astral.sh/uv/) for dependency management
* Windows 10/11, or a current Ubuntu/Debian Linux (see
  [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md) for the exact tested matrix)

## Install

```bash
git clone https://github.com/MdTanjilIslamBappi/vsphere-health-check-v8.git
cd vsphere-health-check-v8

# Linux/macOS
./scripts/linux/install.sh

# Windows PowerShell
.\scripts\windows\install.ps1
```

Both scripts create a project-local virtual environment (`.venv`), install
pinned dependencies from `uv.lock`, install `vhealth` into it, and print
the exact command to run it. `scripts/windows/` and `scripts/linux/` each
hold a matching install/uninstall pair, so you only need to look at the
folder for your own OS.

## Uninstall

```bash
# Linux/macOS
./scripts/linux/uninstall.sh

# Windows PowerShell
.\scripts\windows\uninstall.ps1
```

This removes the `.venv` virtual environment and any local build/test
caches (`dist/`, `build/`, `.pytest_cache/`, etc.) — i.e. everything
`install.sh`/`install.ps1` created. It does **not** remove `uv` or Python
themselves (they're outside this repo and likely used by other projects),
and it does **not** touch any report folders you passed to `vhealth
assess --output ...` — those are your own generated output.

To remove vhealth completely, also delete the folder you cloned the repo
into, and uninstall `uv` itself if you don't need it elsewhere (see
[the uv docs](https://docs.astral.sh/uv/getting-started/installation/#uninstallation)).

## Usage

```bash
vhealth --version

# See what's inside a bundle without running a full assessment
vhealth inspect --input support-bundle.zip

# Run the full assessment and write JSON + reports
vhealth assess --input support-bundle.zip --output ./out

# Re-render reports from a saved assessment.json (no need to re-parse)
vhealth report --assessment ./out/assessment.json --format docx,html --output ./out
```

Optional branding/behaviour overrides go in a TOML config file, passed with
`--config`; see [`src/vhealth/resources/defaults/config.default.toml`](src/vhealth/resources/defaults/config.default.toml)
for every available key and its default.

### Crediting who prepared the report

`assess` and `report` both accept `--engineer`, `--author`, and
`--verifier`, which appear on the cover page of the HTML and DOCX
reports, plus `--revision` (default `V01`) and `--description` (default
"Initial copy") for the report's Version History table:

```bash
vhealth assess --input support-bundle.zip --output ./out \
  --engineer "Jane Doe" --author "Jane Doe" --verifier "John Smith" \
  --revision V02 --description "Re-verified after remediation"
```

Leave `--engineer`/`--author`/`--verifier` off and you'll be prompted for
each interactively (press Enter to skip); pass `--no-prompt` to skip the
prompts entirely and leave them unset, which also happens automatically in
a non-interactive run (CI, a script). `--revision`/`--description` are
never prompted for. None of this is written into `assessment.json` -- a
verifier can add their name on a later `vhealth report` re-render without
re-running the assessment.

### Report layout

Every HTML/DOCX report has the same structure, written as a customer-facing
health check: a cover page, a Version History table, a table of contents,
an Executive Summary, a Scope of Health Check (a single bullet list --
items that need vCenter-level data, such as EVC mode, datastores, VM
inventory, or vCenter alarms, are listed as explicitly not assessed rather
than guessed or silently dropped), and a System Status section: 3.1 an
aggregate hardware-status grid, 3.2 a VMware-components status table plus
"Key Findings at a Glance", 3.3 an ESXi host inventory table (server
model/CPU model/management IP) plus "Detailed Observations", and 3.4
grouped Recommendations. See RULE_CATALOG.md and SUPPORTED_FORMATS.md for
exactly what backs each section.

Every `assess`/`report` run that generates `docx` or `html` also writes a
companion `findings-log.docx`/`findings-log.html` with the full
per-finding detail (evidence lines, remediation, limitations) -- the main
report stays a concise executive read, and nothing is lost.

Log-based findings (PDL/APD/dead-path/ALUA/VOB from `vmkwarning`/`vobd`)
are scoped to the last 90 days of the bundle's own capture date, since
this is meant as a quarterly health check; older matches are still
counted (not discarded) but don't drive an active finding.

## How it works

1. **Ingestion** — the archive is extracted under strict safety limits
   (zip-slip protection, size/entry/compression-ratio caps). See
   [`src/vhealth/security/extraction_guard.py`](src/vhealth/security/extraction_guard.py).
2. **Discovery** — individual ESXi `vm-support` host bundles are located
   inside the extracted tree (a vCenter bundle contains one per host).
3. **Parsing** — a set of parsers read specific command-output files
   (`localcli ... --json`, `smartinfo.txt`, IPMI sensor dumps, rotated
   `vmkwarning`/`vobd` logs) into typed models. See
   [RULE_CATALOG.md](RULE_CATALOG.md) and
   [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md).
4. **Rules** — each rule inspects the parsed data for one host and emits
   zero or more findings with a severity, evidence, remediation and
   documented limitations.
5. **Reporting** — the findings and inventory are rendered into an HTML
   report (Jinja2) and a Word report (python-docx).

Every assessment also writes a versioned, machine-readable `assessment.json`
(see [`ARCHITECTURE.md`](ARCHITECTURE.md)) so two runs of the same bundle,
version and configuration can be diffed meaningfully.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a parser or a rule,
and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[MIT](LICENSE)
