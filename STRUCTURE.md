# Repo layout — conventions to follow

Reference for anyone (human or agent) adding code here. Read this before
creating a new file, so the tree stays coherent as modules get added.

## Tree

```
invoicepilot/
├── pyproject.toml        # deps, [project.scripts], ruff + pytest config
├── STRUCTURE.md          # this file
├── README.md
├── .env.example          # every env var the backend reads
│
├── backend/              # everything importable
│   ├── __main__.py       # `python -m backend` → cli
│   ├── cli.py            # Typer app — run-and-exit entrypoint
│   │
│   ├── core/             # plumbing only, no domain logic
│   │   ├── config.py     # env/settings
│   │   ├── db.py         # engine/session
│   │   └── logging.py
│   │
│   ├── models.py         # ORM tables (one: invoices)
│   ├── schemas.py        # pydantic request/response models
│   ├── accounts.py       # domain: connected mailboxes
│   ├── extract.py        # domain: documents -> invoice fields (pure)
│   ├── gmail.py          # domain: fetch/search/attachments
│   ├── drive.py          # domain: upload/folders
│   ├── unipile.py        # domain: hosted-auth provider + mail transport
│   ├── invoice_store.py  # domain: extracted invoices on disk
│   ├── invoices.py       # domain: extracted invoices in Postgres
│   ├── shares.py         # domain: share links and what a token resolves to
│   ├── share_zip.py      # domain: the download - invoices.csv + the documents
│   ├── share_mail.py     # domain: the mail a share is sent with
│   ├── process.py        # domain: scan orchestration
│   ├── scan_jobs.py      # domain: in-flight scans
│   │
│   └── services/         # run-forever entrypoints
│       └── api.py        # FastAPI app
│
├── frontend/             # the app (Vite + React + TS)
│   ├── index.html        # shell; the app mounts into #root
│   ├── vite.config.ts    # /api → 127.0.0.1:8000 proxy
│   └── src/
│       ├── main.tsx      # picks the page off the URL: /s/<token> or the dashboard
│       ├── routes/       # Dashboard.tsx, SharePage.tsx
│       ├── api/          # client.ts (the only fetch), types.ts
│       ├── components/
│       ├── lib/          # formatting, owner-key storage
│       └── styles/       # tokens.css, dashboard.css, flow.css (the share UI)
│
├── scripts/              # run-and-exit ops tooling, never imported by backend/
├── templates/            # invoice2data extraction templates (data, not code)
├── tests/
├── docker/
└── docs/
```

## Rules

1. **`backend/` = importable, everything else = not.** Entrypoints (CLI, ASGI
   app) live inside `backend/` because they are resolved by import path
   (`backend.cli:main`, `backend.services.api:api`). Only never-imported
   things — ops scripts, tests, deploy config — sit outside it.

2. **`core/` is a leaf.** It may not import from the domain modules. The
   domain imports `core`, never the reverse. If something in `core/` needs
   `backend.process`, it isn't core — move it out.

3. **`core/` is plumbing, not "shared stuff."** Settings, DB, logging, auth.
   Domain code stays at `backend/` root even when several modules use it.
   Never add a `libs/`, `common/`, or `utils/` module — they become junk drawers.

4. **`services/` = runs indefinitely. `scripts/` = runs once and exits.**
   That is the only distinction. A new worker or scheduler goes in
   `services/`; a one-off backfill goes in `scripts/`.

5. **Nothing in `backend/` may import from `backend.services`.** Otherwise the
   CLI drags FastAPI into its startup path. Services import domain modules;
   domain modules never import services.

6. **Split by domain, not by layer.** When a module outgrows one file, it
   becomes a package of its own: `gmail.py` → `gmail/{client,search,attachment}.py`.

7. **`extract.py` stays pure.** No transport, no store, no stdout. It takes
   bytes and a `fetch` callable and returns fields. That is what lets the whole
   extraction ruleset be regression-tested against `.data/` with no network.
   The one exception is `linked_document`, which contacts the vendor's servers
   and is opt-in per call.

8. **Presentation lives in callers, never in `process.py`.** The pipeline
   returns typed results and reports progress through `on_progress`. That is
   the only reason one scan can serve both a terminal report and a polled HTTP
   job. A `print` or a user-facing f-string in a domain module belongs in the
   CLI or the API instead.

## Frontend

Two pages, and still no router. `main.tsx` reads the path once: `/s/<token>`
mounts `SharePage`, everything else mounts `Dashboard`. Neither page navigates
within itself — the share download is a real file and the composer is state —
so a router would be a dependency and a bundle for one `startsWith`. Add one
when a page appears that has to change the URL without a reload. Components stay
flat under `components/`; the two top-level pages live in `routes/`.

`/s/<token>` is served by the same `index.html` as the dashboard: nginx's
SPA catch-all (`try_files $uri $uri/ /index.html`) already sends every non-`/api`
path there, so the token is read off `window.location` in the browser rather
than resolved by a server route. No nginx rule was added.

9. **All network access goes through `api/client.ts`.** Components never call
   `fetch` directly, so base URL, error shape and JSON decoding have one home.

10. **`types.ts` is hand-written**, mirroring `backend/schemas.py`. An earlier
    draft of this file said to generate it from `/openapi.json`; for three
    endpoints that costs a codegen dependency and a step people forget to run,
    to produce types short enough to read in one screen. Revisit if the surface
    grows.

The dev server proxies `/api` to the backend, so the frontend always calls
same-origin paths. Do not add a `VITE_API_URL` base-URL variable — it would
reintroduce the CORS config the proxy exists to avoid.

## Database

Two tables. Everything the parser found is stored in `data` as JSONB — the same
payload `invoice_store` writes to disk — with only `id` and `issued_on` lifted
out as columns, because those are what Postgres has to key and sort on.

`shares` is the second, and the only thing in the product that Postgres is the
source of truth for besides the invoices themselves: a link has to outlive the
process that made it, and no other system knows it exists. It keeps the same
shape — the ids it covers are a JSONB snapshot rather than a join table, so
there is no query in the share flow that is not a primary-key lookup.

11. **Do not add a table per concept.** Connected mailboxes live in Unipile,
    which is their source of truth; copying them into Postgres would only give
    the two a way to disagree. In-flight scans live in memory, because they are
    worth nothing once the process ends.
