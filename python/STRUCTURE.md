# Python layout — conventions to follow

Reference for anyone (human or agent) adding code under `python/`. Read this
before creating a new file, so the tree stays coherent as modules get added.

## Tree

```
python/
├── pyproject.toml        # deps, [project.scripts], ruff + pytest config
├── STRUCTURE.md          # this file
├── README.md
├── .env.example          # Python-only vars; repo-root .env holds the shared ones
│
├── app/                  # everything importable
│   ├── __main__.py       # `python -m app` → cli
│   ├── cli.py            # Typer app — run-and-exit entrypoint
│   │
│   ├── core/             # plumbing only, no domain logic
│   │   ├── config.py     # env/settings
│   │   ├── db.py         # engine/session
│   │   └── logging.py
│   │
│   ├── models.py         # domain types / ORM tables
│   ├── schemas.py        # pydantic request/response models
│   ├── gmail.py          # domain: fetch/search/attachments
│   ├── drive.py          # domain: upload/folders
│   ├── process.py        # domain: job orchestration
│   │
│   └── services/         # run-forever entrypoints
│       └── api.py        # FastAPI app
│
├── scripts/              # run-and-exit ops tooling, never imported by app/
└── tests/
```

## Rules

1. **`app/` = importable, everything else = not.** Entrypoints (CLI, ASGI app)
   live inside `app/` because they are resolved by import path
   (`app.cli:main`, `app.services.api:api`). Only never-imported things —
   ops scripts, tests, deploy config — sit outside it.

2. **`core/` is a leaf.** It may not import from the domain modules. The
   domain imports `core`, never the reverse. If something in `core/` needs
   `app.process`, it isn't core — move it out.

3. **`core/` is plumbing, not "shared stuff."** Settings, DB, logging, auth.
   Domain code stays at `app/` root even when several modules use it.
   Never add a `libs/`, `common/`, or `utils/` module — they become junk drawers.

4. **`services/` = runs indefinitely. `scripts/` = runs once and exits.**
   That is the only distinction. A new worker or scheduler goes in
   `services/`; a one-off backfill goes in `scripts/`.

5. **Nothing in `app/` may import from `app.services`.** Otherwise the CLI
   drags FastAPI into its startup path. Services import domain modules;
   domain modules never import services.

6. **Split by domain, not by layer.** When a module outgrows one file, it
   becomes a package of its own: `gmail.py` → `gmail/{client,search,attachment}.py`.
   This mirrors the Rust side's `src/gmail/`, `src/drive/`, `src/process/` —
   keeping the two trees aligned is worth preserving.

## Open decisions

- **Database ownership.** `models.py` is an empty `Base` on purpose: unresolved
  whether the Python side shares the Rust binary's Postgres schema (models must
  then mirror the existing tables) or gets its own database.
