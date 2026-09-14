# Setup

## Requirements

Homebrew Python 3.12. The system Python at `/usr/bin/python3` is 3.9 and is not used.

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 --version
```

## Create the environment

```bash
cd ~/projects/olympic-medal-trends
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

`requirements.txt` holds the direct dependencies. `requirements-lock.txt` is a `pip freeze`
of the environment that produced the results, and is the file to use for an exact rebuild.

## Get the data

```bash
./.venv/bin/python scripts/download_data.py
```

One file, roughly 36 MB, no account and no API key. The script verifies size and sha256
and does nothing if the file is already present and correct. Everything under `data/` is
excluded from git, so this step is required on a fresh clone.

## Run the tests

```bash
./.venv/bin/python -m pytest -q
```

## Checks before pushing

```bash
./.venv/bin/python scripts/check_prose.py
./.venv/bin/python scripts/verify_readme.py
```

The first asserts that no dash character appears in the prose of any tracked markdown file.
The second asserts that every headline number in the README also appears in the JSON report
that produced it, so a retyped figure or a stale figure fails loudly.

## Push one phase

```bash
./scripts/push.sh 1 "clean the data and build the country map"
```

Refuses to run if anything under `data/` is staged.
