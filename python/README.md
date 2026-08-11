# Invoice Pilot — Python

Python CLI and API alongside the Rust crate. See [STRUCTURE.md](STRUCTURE.md)
for the layout conventions.

## Setup

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
```

Settings are read from the repo-root `.env` first, then `python/.env`
(see [.env.example](.env.example)).

## CLI

```bash
invoicepilot-py --help     # installed entrypoint
python -m app --help       # equivalent, no install needed
```

## API

```bash
./scripts/run_api.sh       # http://127.0.0.1:8000/health
```

## Tests

```bash
pytest
```
