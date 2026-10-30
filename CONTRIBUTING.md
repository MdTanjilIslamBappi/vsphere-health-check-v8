# Contributing

## Setup

```bash
git clone <repo-url>
cd vmware-health-assessment
./scripts/install.sh        # or scripts\install.ps1 on Windows
uv sync --group dev          # adds pytest, ruff on top of the runtime deps
```

## Running checks locally

```bash
uv run python -m pytest -q
uv run python -m pytest --cov=vhealth --cov-report=term-missing
uv run ruff check .
```

`python -m pytest` is used instead of the bare `pytest` entry-point script
because some locked-down Windows machines (this one included, under a
Windows Application Control/WDAC policy) block execution of freshly
generated `.exe` console-script shims while happily running the same code
through `python.exe -m`. Either form works where no such policy exists.

All of the above must pass before opening a PR. CI runs the same
commands on the supported OS/Python matrix (see `.github/workflows/ci.yml`
and `SUPPORTED_FORMATS.md`).

## Adding a parser

1. Add `src/vhealth/parsers/<name>.py` with a module-level `VERSION`
   string and a `parse(host_dir: Path, host: HostInfo) -> list[str]`
   function. It must enrich `host` in place and return a list of warning
   strings -- it must never raise for missing/malformed input.
2. Register it in `src/vhealth/parsers/__init__.py`'s `PARSER_MODULES`.
3. Add the source file(s) it reads to `_EVIDENCE_RELATIVE_PATHS` in
   `src/vhealth/pipeline.py` if they should appear in the evidence
   manifest.
4. Document the source file format and known gaps in
   `SUPPORTED_FORMATS.md`.
5. Add unit tests in `tests/unit/test_parsers.py`, extending
   `tests/fixtures/synthetic_bundle.py` if the existing synthetic fixture
   doesn't cover the new data.
6. Bump `VERSION` whenever you change what a parser extracts in a way
   that could change existing findings, so two assessment runs across an
   app upgrade stay explainable (see "Reproducibility" in
   `ARCHITECTURE.md`).

## Adding a rule

See the "Adding a rule" section in `RULE_CATALOG.md` -- it is the
authoritative checklist (evidence prerequisites, limitations, a
RULE_CATALOG.md row, and a passing/failing unit test pair are all
required in the same change).

## Test fixtures: no customer data

Never commit a real customer support bundle, or any file derived from
one, to this repository -- not as a test fixture, not in an issue, not in
a commit message. Use or extend
`tests/fixtures/synthetic_bundle.py` instead. If a bug can only be
reproduced against real-world data, describe the structure/content that
triggers it (file layout, the specific log line pattern, etc.) rather
than attaching the data itself.

## Coding conventions

* Python 3.11+, type hints throughout (`py.typed` is shipped).
* `ruff check .` must pass (rule set: `E`, `F`, `I`, `UP`, `B`; see
  `pyproject.toml`).
* No new runtime dependency without a one-line justification in the PR
  description (maintenance activity, license, why the stdlib/existing
  deps don't cover it).
* Don't add exception handling for cases that can't happen; do add it
  (with a clear, actionable message) at every boundary that reads
  untrusted bundle content.

## Release process

1. Update `CHANGELOG.md`.
2. Bump `version` in `pyproject.toml` (and `src/vhealth/__init__.py`).
3. `uv lock` if dependencies changed, and commit the updated `uv.lock`.
4. Tag the release; CI builds/tests must be green on the tag.
5. Portable executables (once that work lands) are attached to the
   GitHub release, not committed to the repository.
