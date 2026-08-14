[![Python](https://img.shields.io/badge/python-%23000000.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/fastapi-%23000000.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vite](https://img.shields.io/badge/vite-%23000000.svg?style=for-the-badge&logo=vite&logoColor=white)](https://vite.dev)
[![Docker](https://img.shields.io/badge/docker-%23000000.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%23000000.svg?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)

[![Invoice Pilot](https://img.shields.io/badge/invoicepilot-7f56da)](https://meetneura.ai) [![Powered by Neura AI](https://img.shields.io/badge/Powered%20by-Neura%20AI-7f56da)](https://meetneura.ai)

# Invoice Pilot

Automated invoice and bank statement management: pulls documents out of your
mailbox, extracts the fields, and organizes them. Free to use, modify and
distribute under the MIT License.

![Demo](docs/assets/demo.png)

> **Status.** Invoice Pilot was originally a Rust TUI. It is being rewritten as
> a Python backend with a web dashboard, and that rewrite is in progress — see
> [Current state](#current-state) for what actually runs today.

## Table of Contents

- [Current state](#current-state)
- [Layout](#layout)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running](#running)
- [Configuration](#configuration)
- [Invoice extraction](#invoice-extraction)
- [Supported financial institutions](#supported-financial-institutions)
- [Development](#development)
- [Security notes](#security-notes)
- [Contributing](#contributing)
- [License](#license)

## Current state

Working today:

- **Dashboard** — React app listing stored invoices (vendor, amount, issued).
  **Update** scans the 20 most recent messages in every connected mailbox and
  the table refreshes with whatever parsed. **Add source** runs the hosted
  Unipile wizard to connect a new mailbox.
- **Extraction pipeline** — mail through Unipile, `invoice2data` over
  attachments, forwarded `.eml` contents, message bodies and PDFs linked from
  a body. Shared by the API and `scripts/parse_invoices.py`.
- **Storage** — Postgres for the metadata the dashboard queries, plus
  `.data/<mailbox>/<date>__<vendor>__<amount>__<id>/` for the vendor's own
  document. Both are keyed identically, so re-scanning updates rather than
  duplicates.
- **API** — `/health`, `/accounts`, `/accounts/connect`, `/scan`,
  `/scan/{id}`, `/invoices`.
- **CLI** — `invoicepilot version`, `invoicepilot config`.

Not yet built: preview/download of a stored document, selection actions,
pagination, and sorting by column — the dashboard renders those controls but
they are inert. Not yet ported from the Rust version: Google Drive upload,
institution-based folder organization, scheduled runs and completion emails
(`backend/drive.py` and `backend/gmail.py` are placeholders).

## Layout

```
backend/     Python package — CLI, FastAPI service, domain modules
frontend/    Vite-served dashboard
scripts/     run-and-exit ops tooling
templates/   invoice2data extraction templates
tests/       pytest suite
docker/      Dockerfiles, one compose file, nginx config
```

See [STRUCTURE.md](STRUCTURE.md) for the rules governing where new code goes.

## Prerequisites

- **Python 3.11+**
- **Node 20+** (only for the dashboard)
- **Just** — optional, see <https://github.com/casey/just#installation>
- **Docker** — only if you want the Postgres container
- A **Unipile** account (brokers the mailbox OAuth), or a Google Cloud project
  with the Gmail API enabled if you want to go direct

### Google Cloud setup (direct Gmail path only)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create
   or select a project
2. Enable the **Gmail API** under "APIs & Services" > "Library"
3. Create OAuth2 credentials: "Credentials" > "Create Credentials" >
   "OAuth client ID", application type **Desktop app**
4. Save the **Client ID** and **Client Secret** into `.env`
5. Under "OAuth consent screen", add the scope
   `https://www.googleapis.com/auth/gmail.readonly`, and while the screen is in
   "Testing" mode add your own address under **Test users**
6. Add `http://localhost:57553` to the client's **Authorized redirect URIs**.
   It must byte-match `GOOGLE_GMAIL_REDIRECT_URI` — http not https, no trailing
   slash, no path.

Using Unipile instead means none of the above is needed; Unipile brokers the
provider OAuth and you only set `UNIPILE_API_KEY` and `UNIPILE_DSN`.

## Setup

```bash
cp .env.example .env      # then fill in your credentials
just setup                # or: ./scripts/bootstrap.sh
source .venv/bin/activate

just start-db             # Postgres in Docker, port 57552
just migrate              # create tables, backfill anything already in .data/

just web-install          # npm install in frontend/
```

`bootstrap.sh` uses `uv` if it is installed and falls back to `venv` + `pip`.
`just migrate` needs `DATABASE_URL` set and the database running.

## Running

```bash
just api                  # FastAPI on http://127.0.0.1:8000  (/health)
just web                  # dashboard on http://localhost:5173 (dev server)
just web-deploy           # dashboard on http://localhost:8090 (built, in Docker)
just cli config           # show resolved settings, secrets redacted
just test                 # pytest
just lint                 # ruff check + format --check
```

Without `just`:

```bash
./scripts/run_api.sh
cd frontend && npm install && npm run dev
python -m backend --help
```

Run `just api` and `just web` together: the Vite dev server proxies `/api` to
the backend, so the dashboard calls same-origin paths and neither CORS config
nor a base-URL variable is needed.

`just web-deploy` is the same dashboard built and served by nginx in a
container on port 8090, with the same same-origin `/api` (proxied to the host's
port 8000 rather than to Vite). The container holds a build, not the source, so
rerun it after a frontend change or 8090 goes on serving the previous bundle.
The API itself still runs on the host: only the dashboard is containerised.

A scan runs in a background thread and the dashboard polls it. A small mailbox
finishes in a few seconds, but the work is unbounded in principle — it
downloads every PDF attachment, runs invoice2data over each candidate document,
and by default follows invoice links out to the vendor's own servers with a 20s
timeout each. Pass `--no-follow-links` to the CLI (or `{"follow_links": false}`
to `POST /scan`) to keep a scan strictly offline.

### Containers

[docker/compose.yml](docker/compose.yml) holds the two services this project
runs in Docker, and `docker/.env` holds their credentials, which is why every
command below passes `--env-file .env`.

```bash
just start-db             # postgres service, port 57552
just stop-db
just web-deploy           # web service, port 8090, rebuilding the image
just web-down
```

The API is deliberately not a service. It runs on the host under uvicorn, and
the dashboard container's nginx proxies `/api` to it through
`host.docker.internal`; containerising it would mean rebuilding an image on
every backend edit.

## Configuration

All settings come from a single `.env` at the repo root, read by
[backend/core/config.py](backend/core/config.py). Every key it reads is
documented in [.env.example](.env.example).

Keys carried over from the Rust binary that nothing reads yet (Drive upload,
scheduling, keyword filters, Wise, notification email) are listed at the bottom
of `.env.example`, commented out and marked as such.

## Invoice extraction

```bash
python scripts/parse_invoices.py --help
```

Documents are matched against `invoice2data` templates: 215 built-in ones, plus
any YAML you add under [templates/invoice2data/](templates/invoice2data/), which
is auto-loaded. Point `--templates` elsewhere to override.

Recognised invoices are written under `.data/`, one directory per invoice
holding `invoice.json`, the original `invoice.pdf` (when there was an
attachment) and `source.html`. **`.data/` is gitignored** — it holds real
financial documents.

## Supported financial institutions

Detection covers digital banks (Wise, Revolut, Nubank, Bunq, Monzo, Starling,
Chime), traditional banks (Santander, BBVA, CaixaBank, ING, Deutsche Bank, HSBC,
Barclays and most major European banks), brokerages (Interactive Brokers,
Charles Schwab, E\*TRADE, TD Ameritrade, Fidelity, Robinhood, Webull), crypto
exchanges (Coinbase, Binance, Kraken) and payment processors (Stripe, PayPal,
Adyen, Mollie).

> This detection logic lived in the Rust binary and has **not** been ported yet.
> It is documented here as the target behaviour, not as a current feature.

## Development

```bash
just test                 # pytest
just lint                 # ruff check + ruff format --check
just fmt                  # apply autofixes and formatting
just clean                # drop venv, caches, frontend build output
```

CI runs the same lint and test steps plus a frontend build — see
[.github/workflows/ci.yml](.github/workflows/ci.yml).

## Security notes

- Never commit `.env` or extracted documents; both are gitignored
- `.data/` contains real invoices — treat it as sensitive
- OAuth callbacks are loopback-only
- All provider API calls use HTTPS

## Contributing

1. **Fork** the repository on GitHub
2. **Branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**, following [STRUCTURE.md](STRUCTURE.md) for placement
   and adding tests where applicable
4. **Check**: `just lint && just test`
5. **Commit**: `git commit -m 'feat: add amazing feature'`
6. **Open a Pull Request** describing the change

Useful places to start: porting the Drive upload and institution-detection
logic, defining the dashboard's API endpoints in `backend/schemas.py`, adding
`invoice2data` templates for vendors that don't parse yet, or widening test
coverage.

Report bugs via the GitHub issue tracker with steps to reproduce, expected
behaviour and actual behaviour.

## License

MIT — see [LICENSE](LICENSE). Completely free to use, modify and distribute for
any purpose.
