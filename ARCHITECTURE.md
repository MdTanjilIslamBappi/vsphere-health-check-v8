# Architecture

## Pipeline

```
input.zip/.tgz
      |
      v
  ingestion/extract.py     -- safe extraction (zip-slip, size/ratio limits)
      |
      v
  discovery/bundle.py      -- find one or more ESXi vm-support host dirs
      |
      v
  correlation/build.py     -- run every parser over each host dir -> HostInfo
      |
      v
  rules/registry.py        -- run every rule over each HostInfo -> Finding[]
      |
      v
  models/assessment.py     -- Assessment (metadata + hosts + findings)
      |
      +--> assessment.json  (versioned, schema v1.0.0)
      |
      +--> reporting/html_report.py  -> report.html
      |
      +--> reporting/docx_report.py  -> report.docx
```

`src/vhealth/pipeline.py` (`run_assessment`) is the single function that
wires these stages together; `cli.py` only parses arguments and calls it.

## Why resources live inside the package

The suggested top-level repo layout in the project's requirements shows a
`resources/` directory alongside `src/`. This repository instead keeps
templates, the default config, and the JSON schema under
`src/vhealth/resources/` (a real Python subpackage), loaded via
`importlib.resources`.

This was a deliberate deviation, not an oversight: the requirements
themselves say to keep runtime resources "inside the installed Python
package or another packaging mechanism that reliably includes them" and
not to assume files outside the installed package will always be
available. A top-level `resources/` directory requires either a build-tool
mapping (hatchling `force-include`, in this case) to end up inside the
wheel *and* a separate code path to find it in an editable/dev install --
two mechanisms that can drift out of sync. Putting the files directly
inside the package collapses that to one mechanism that is correct by
construction in both modes, which is what `vhealth assess` run from an
arbitrary working directory, or after installation outside the repo,
actually depends on.

## Models (`vhealth.models`)

* `HostInfo` -- one ESXi host's normalised, parsed data. Parsers mutate
  this in place; nothing else does.
* `Finding` -- one rule's output: severity, evidence, remediation,
  documented limitations.
* `Assessment` -- `AssessmentMetadata` (reproducibility/execution info,
  see below) + `hosts` + `findings`.

## Reproducibility (`AssessmentMetadata`)

Everything in `AssessmentMetadata` except `assessment_timestamp` is a pure
function of (input bytes, app version, rule catalogue, config). Two runs
of `vhealth assess` against the same bundle, version, and config should
therefore produce identical `hosts`/`findings`, which the
`test_run_assessment_is_deterministic_apart_from_timestamp` integration
test checks directly. `config_fingerprint` is a SHA-256 of the resolved
config (defaults + any `--config` overlay) so a config change that
affects results is visible without diffing TOML files.

`HostInfo.bundle_source` intentionally stores the bundle's *directory
name* (e.g. `esx-HOSTNAME-2026-10-27--08.00-1234567`), not an absolute
path: extraction happens into a freshly randomised temp directory on
every run, so an absolute path there would make two otherwise-identical
assessments fail a byte-for-byte comparison for no meaningful reason.

## Rules (`vhealth.rules`)

A `Rule` is a dataclass wrapping a plain function
`HostInfo -> list[Finding]`, plus the metadata required by
`CONTRIBUTING.md` for every rule (`evidence_required`, `limitations`).
`Rule.run()` catches any exception from the rule function itself so one
broken rule can't abort the rest of the assessment -- it surfaces as an
`INFO`-severity finding naming itself instead.

## Security (`vhealth.security`)

`extraction_guard.py` is the only place that decides whether an archive
member is safe to write, and both the ZIP and tar code paths in
`ingestion/extract.py` call through it. See its module docstring and
`tests/security/` for what it defends against (path traversal,
decompression bombs, oversized members, Windows `MAX_PATH`).
