# Offline installation package

For an isolated/air-gapped target machine with no network access at all,
prepare a package on a connected workstation and transfer it.

## 1. On a connected workstation, build the package

```bash
cd vmware-health-assessment
mkdir offline-package

# The vhealth wheel + sdist
uv build --out-dir offline-package

# Every runtime dependency, pinned and hashed from the committed uv.lock
uv export --no-dev --no-emit-project --format requirements-txt \
    -o offline-package/requirements.txt

# The actual dependency wheels (uv has no "pip download" equivalent, so
# this borrows pip for one invocation without adding it to the project)
mkdir offline-package/wheels
uv run --with pip -- python -m pip download \
    -r offline-package/requirements.txt -d offline-package/wheels --no-deps
cp offline-package/vhealth-*-py3-none-any.whl offline-package/wheels/
```

`offline-package/wheels` now contains every wheel vhealth needs,
pinned to exactly what's in `uv.lock`.

## 2. Transfer

Copy the `offline-package/` directory to the target machine by whatever
sanctioned method your environment uses (USB, internal file transfer,
etc.). Nothing in it is customer data.

## 3. On the isolated target machine

```bash
uv venv --python 3.12 .venv
uv pip install --offline --python .venv --no-index \
    --find-links /path/to/offline-package/wheels vhealth
```

`--offline --no-index` makes uv refuse to contact any package index;
installation only succeeds if everything resolves from `--find-links`.

## Validated

The full sequence above (steps 1-3) was run end to end on Windows
11/Python 3.12: `uv build`, `uv export --no-emit-project`,
`pip download --no-deps` for all 10 runtime dependencies, and a
`--offline --no-index` install from the local wheel directory into a
brand-new venv. The installed package imports and its CLI logic runs
correctly (verified via `python -m vhealth.cli --version`).

**Known gap:** on this machine, invoking the generated
`vhealth.exe` console-script shim directly (rather than importing the
package through Python) was blocked by a local Windows Application
Control policy -- the same policy that also blocked `pytest.exe` during
test runs in this project's own CI-equivalent local verification. This
is an endpoint-security policy on that specific machine, not a defect in
the package: `python -m vhealth.cli ...` (or an unblocked/allow-listed
`.venv\Scripts\vhealth.exe`) both work. If you deploy to a locked-down
corporate Windows image, confirm your organisation's Application
Control/WDAC policy allow-lists Python console-script executables
created by `pip`/`uv`, or invoke vhealth via `python -m vhealth.cli`
instead.

**Not yet done:** this has only been exercised on Windows; a Linux
offline-install pass (wheels will differ for any platform-specific
dependency) has not been attempted yet.
