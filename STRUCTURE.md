# Repo layout — conventions to follow

Reference for anyone (human or agent) adding code here. Read this before
creating a new file, so the tree stays coherent as modules and services get
added.

## Tree

```
invoicepilot/
├── compose.yml                     # dev:  postgres + web
├── compose.prod.yml                # prod: postgres + api + web
├── .env.example                    # compose interpolation vars
├── justfile                        # the only file that spans services
├── ruff.toml                       # repo-wide lint config
├── README.md  STRUCTURE.md  CHANGELOG.md  LICENSE
├── docs/                           # assets/  flows/  ui-sketches/
│
├── deploy/
│   └── caddy-public.caddy          # host TLS vhost — not a container
│
├── tools/                          # dev tooling, owned by no service
│   ├── preview_flows.py
│   └── cloudcli/                   # Dockerfile + compose.yml
│
└── services/
    ├── drafter/            # runs Claude Code; drafts a template, knows no domain
    ├── api/
    │   ├── Dockerfile
    │   ├── .dockerignore
    │   ├── entrypoint.sh
    │   ├── pyproject.toml          # deps, [project.scripts], pytest config
    │   ├── .python-version
    │   ├── .env.example
    │   ├── tests/
    │   ├── scripts/                # ops tooling: run once, exit
    │   └── src/
    │       └── invoicepilot/       # the import package
    │           ├── __main__.py     # `python -m invoicepilot` → cli
    │           ├── cli.py          # Typer app — run-and-exit entrypoint
    │           ├── app.py          # FastAPI app — the served entrypoint
    │           │
    │           ├── core/           # plumbing only, no domain logic
    │           │   ├── config.py   # env/settings
    │           │   ├── db.py       # engine/session
    │           │   └── logging.py
    │           │
    │           ├── templates/      # invoice2data YAML (package data)
    │           │
    │           ├── models.py       # ORM tables
    │           ├── schemas.py      # pydantic request/response models
    │           ├── migrate.py      # schema creation + backfill (`invoicepilot migrate`)
    │           ├── accounts.py     # domain: connected mailboxes
    │           ├── extract.py      # domain: documents -> invoice fields (pure)
    │           ├── gate.py         # domain: is this message an invoice at all
    │           ├── learn.py        # domain: draft a template for an untaught issuer
    │           ├── unipile.py      # domain: hosted-auth provider + mail transport
    │           ├── invoice_store.py# domain: extracted invoices on disk
    │           ├── invoices.py     # domain: extracted invoices in Postgres
    │           ├── mailboxes.py    # domain: how far each mailbox is scanned
    │           ├── workspaces.py   # domain: whose data is whose — the cookie, and mailbox ownership
    │           ├── shares.py       # domain: share links and what a token resolves to
    │           ├── share_zip.py    # domain: the download — invoices.csv + the documents
    │           ├── share_mail.py   # domain: the mail a share is sent with
    │           ├── process.py      # domain: scan orchestration
    │           └── scan_jobs.py    # domain: in-flight scans
    │
    └── web/
        ├── Dockerfile
        ├── .dockerignore
        ├── Caddyfile               # serves the bundle, proxies /api
        ├── package.json  package-lock.json
        ├── vite.config.ts          # /api → 127.0.0.1:8000 proxy
        ├── tsconfig.json  index.html
        └── src/
            ├── main.tsx            # picks the page off the URL
            ├── routes/             # Dashboard.tsx  SharePage.tsx
            ├── components/
            ├── api/                # client.ts (the only fetch), types.ts
            ├── lib/                # formatting, owner-key storage
            └── styles/             # tokens.css, dashboard.css, flow.css
```

## Repo rules

1. **The root owns nothing service-specific.** Everything at top level is
   either cross-cutting (`compose*.yml`, `justfile`, `ruff.toml`) or shared
   (`docs/`). The moment a root file is only meaningful to one service, it
   belongs inside that service. This is the rule the old layout broke:
   `pyproject.toml`, `tests/` and `templates/` sat at the root but were the
   backend's alone, which is why the repo read as a Python project with a
   frontend folder rather than two peers.

2. **A service folder is self-contained.** Source, manifest, Dockerfile, server
   config, tests, env example. Deleting a service is one `rm -rf` and one
   compose stanza. No service reads a file from another service's folder — if
   two need the same thing, see rule 8.

3. **Folder name == compose service name.** `services/api` is the `api:` in
   `compose.yml`. One-to-one, no translation table.

4. **Nothing inside a package reaches upward.** A module may compute paths
   *down* from itself (`Path(__file__).parent / "templates"`) but never *up*
   into a parent directory. Upward paths only work by accident of the checkout
   layout and break in an installed wheel. Anything a package needs is either
   packaged with it, or comes from settings.

5. **Off-the-shelf images get no folder.** `postgres` has no source and no
   Dockerfile, so it exists only in compose. It earns `services/postgres/` the
   day it needs init SQL.

6. **`services/` runs forever in a container. `tools/` is not part of the
   product.** CloudCLI has a Dockerfile and a compose file and still lives in
   `tools/`, because it drives this machine rather than serving InvoicePilot.
   Otherwise `services/` degrades into "things with a Dockerfile".

7. **`deploy/` is host-level config that isn't a container.** Today that is the
   public Caddy vhost, which belongs to whatever already owns :443 on the box.
   A systemd unit or a backup script would go here too.

8. **No `packages/` until two services share code.** Nothing is shared today —
   one service is Python, the other TypeScript. When a second Python service
   appears, the domain modules move to `packages/invoicepilot/` and both
   services become a Dockerfile plus an entrypoint. Do not build that seam
   before there is a second consumer.

## Adding a new service

### First, decide it is one

A service is a container this product runs indefinitely. Check in order:

| It is | Put it in |
|---|---|
| a persistent container InvoicePilot needs | `services/<name>/` |
| an unmodified public image | `compose.yml` only, no folder |
| a container that drives your machine, not the product | `tools/<name>/` |
| something that runs once and exits | `services/<owner>/scripts/`, or a CLI subcommand |
| host config for something outside the stack | `deploy/` |

### Then create it

Name it for what it does — `worker`, `scheduler`, `web` — never for a layer.
`backend` stops working the day a second Python service exists, which is
exactly the situation this layout is built for.

```
services/<name>/
├── Dockerfile          # build context is this directory, nothing above it
├── .dockerignore
├── <manifest>          # pyproject.toml, package.json, …
├── .env.example        # every variable this service reads, with comments
├── tests/
└── src/
```

`src/` for every service, whatever the language. Python's import package sits
one level inside it (`src/<package>/`), which is what makes the api and web
trees read the same shape.

### Then wire it up, in this order

1. **`compose.yml`** — the dev stanza. Only add it here if a developer needs it
   running locally; the api is deliberately absent from the dev file because it
   runs on the host under `--reload`.
2. **`compose.prod.yml`** — the deployed stanza. Needs `restart:
   unless-stopped`, a `healthcheck`, and `depends_on` with
   `condition: service_healthy` for anything it cannot start without.
3. **Ports** — publish nothing in `compose.prod.yml` unless the internet must
   reach it, and then only on `127.0.0.1:` with the host's Caddy in front.
   Services reach each other by compose service name, which never goes through
   a published port.
4. **`justfile`** — the recipes a person types. Follow the existing naming:
   `<service>` runs it in dev, `<service>-build` builds it.
5. **This file** — add it to the tree and say in one line what it is.

There is no CI to add a job to. It was removed deliberately: nothing here is
released on a schedule and one person runs the deploy, so `just lint` and
`just test` before a commit are the whole gate. The cost is that a service
with no local run is a service that breaks silently — see the note in
README.md about the isolation tests, which skip rather than fail when no
database is configured.

### Rules for the service itself

9. **A service declares its config in its own `.env.example`.** Every variable
   it reads, with a comment saying what breaks when it is wrong. That file is
   the contract; the compose stanza is one caller of it.

10. **Secrets are passed in, never read across folders.** A service never opens
    another service's `.env`. Compose passes what it needs through
    `environment:`.

11. **Health is a real endpoint.** `depends_on` without `condition:
    service_healthy` only waits for the container to start, not for the process
    to be able to answer. That distinction is the difference between a clean
    `up` and a race that fails once in ten.

## Inside the api service

12. **`src/invoicepilot/` is importable; everything beside it is not.**
    Entrypoints (CLI, ASGI app) live inside the package because they are
    resolved by import path (`invoicepilot.cli:main`, `invoicepilot.app:api`).
    Only never-imported things — ops scripts, tests, the Dockerfile — sit
    outside it.

13. **`core/` is a leaf.** It may not import from the domain modules. The
    domain imports `core`, never the reverse. If something in `core/` needs
    `invoicepilot.process`, it isn't core — move it out.

14. **`core/` is plumbing, not "shared stuff."** Settings, DB, logging, auth.
    Domain code stays at the package root even when several modules use it.
    Never add a `libs/`, `common/`, or `utils/` module — they become junk drawers.

15. **Nothing may import `app.py`.** Otherwise the CLI drags FastAPI into its
    startup path. `app.py` imports domain modules; domain modules never import
    `app.py`.

16. **Split by domain, not by layer.** When a module outgrows one file, it
    becomes a package of its own: `gmail.py` → `gmail/{client,search,attachment}.py`.

17. **`extract.py` stays pure.** No transport, no store, no stdout. It takes
    bytes and a `fetch` callable and returns fields. That is what lets the whole
    extraction ruleset be regression-tested with no network. The one exception
    is `linked_document`, which contacts the vendor's servers and is opt-in per
    call.

18. **Presentation lives in callers, never in `process.py`.** The pipeline
    returns typed results and reports progress through `on_progress`. That is
    the only reason one scan can serve both a terminal report and a polled HTTP
    job. A `print` or a user-facing f-string in a domain module belongs in the
    CLI or the API instead.

19. **`scripts/` runs once and exits, and is never imported.** A one-off
    backfill goes here. If a script has to run inside the container — as schema
    creation does at startup — make it a CLI subcommand instead, so the image
    does not have to copy a script out of `scripts/` to reach it.

### Where the api's data lives

`templates/` is package data: it ships in the wheel and is read with a downward
path from `extract.py`. It is not a sibling directory, because rule 4.

The extracted documents are **not** in the package. Their root comes from
settings (`data_dir`), which is what lets the container mount a volume at a
path the source layout knows nothing about. Never compute that path from
`__file__`.

## Frontend

Two pages, and still no router. `main.tsx` reads the path once: `/s/<token>`
mounts `SharePage`, everything else mounts `Dashboard`. Neither page navigates
within itself — the share download is a real file and the composer is state —
so a router would be a dependency and a bundle for one `startsWith`. Add one
when a page appears that has to change the URL without a reload. Components stay
flat under `components/`; the two top-level pages live in `routes/`.

`/s/<token>` is served by the same `index.html` as the dashboard: the SPA
catch-all in [services/web/Caddyfile](services/web/Caddyfile) (`try_files
{path} /index.html`) already sends every non-`/api` path there, so the token is
read off `window.location` in the browser rather than resolved by a server
route. No server rule was added for it.

20. **All network access goes through `api/client.ts`.** Components never call
    `fetch` directly, so base URL, error shape and JSON decoding have one home.

21. **`types.ts` is hand-written**, mirroring the api's `schemas.py`. An earlier
    draft of this file said to generate it from `/openapi.json`; for three
    endpoints that costs a codegen dependency and a step people forget to run,
    to produce types short enough to read in one screen. Revisit if the surface
    grows.

The dev server proxies `/api` to the backend, so the frontend always calls
same-origin paths. Do not add a `VITE_API_URL` base-URL variable — it would
reintroduce the CORS config the proxy exists to avoid.

## Configuration

Two `.env` files, and they overlap on purpose:

- **`.env` at the root** is read by compose, for interpolation into the prod
  stanzas.
- **`services/api/.env`** is read by pydantic-settings when the api runs on the
  host under `--reload`, which is the dev workflow.

The same credential appears in both, because the api runs both ways. That is
the cost of keeping `uvicorn --reload` on the host; it is not worth a secrets
manager at this size, but do not add a third copy.

## Database

Six tables, three of them the workspace scoping. Everything the parser found is
stored in `data` as JSONB — the same payload `invoice_store` writes to disk —
with only `id` and `issued_on` lifted out as columns, because those are what
Postgres has to key and sort on.

There is no Alembic. `migrate.run()` calls `create_all`, which creates missing
tables but never alters an existing one, so a change to a table that already
holds rows is written out as guarded DDL in `migrate.py` and keyed off the
catalog rather than a version number. That is affordable while such changes are
rare; a second one that cannot be expressed this way is the signal to add a
migration tool rather than a second special case.

`shares` is the second, and the only thing in the product that Postgres is the
source of truth for besides the invoices themselves: a link has to outlive the
process that made it, and no other system knows it exists. It keeps the same
shape — the ids it covers are a JSONB snapshot rather than a join table, so
there is no query in the share flow that is not a primary-key lookup.

22. **Do not add a table per concept.** Connected mailboxes live in Unipile,
    which is their source of truth; copying them into Postgres would only give
    the two a way to disagree. In-flight scans live in memory, because they are
    worth nothing once the process ends.

    `workspace_accounts` is the one exception, and the test it passed is worth
    keeping: it records *which workspace owns* an account, which is not a copy
    of anything. There is one Unipile tenant and one API key for the whole
    deployment, so every visitor's mailbox lands in the same list and Unipile
    cannot answer whose it is. Status, address and credentials are still read
    from Unipile and still not stored. A table earns its place when it holds a
    fact no other system has, not when it mirrors one that does.

23. **Everything user-facing is scoped to a workspace.** The dashboard is
    served on a public URL with no login, so a query without a `workspace_id`
    filter is a data leak rather than an oversight. `invoicepilot/workspaces.py`
    owns the identity — an httpOnly cookie, minted lazily, unguessable, with no
    recovery by design. Two rules follow from it:

    - **The scope comes from the request, except behind `/s/{token}`.** A share
      recipient holds the link and has their own empty workspace or none, so
      those routes read `share.workspace_id` off the row. Reading the cookie
      there makes every link ever sent resolve to an empty manifest.
    - **`workspace_id` is part of the key wherever the rest of the key comes
      from the mail.** `invoices` and `mailbox_scans` are keyed on the pair
      because an invoice id is derived from the message and two workspaces
      scanning one mailbox agree on it exactly. `shares` is not, because a
      token is already unique.
