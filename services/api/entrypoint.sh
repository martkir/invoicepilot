#!/bin/sh
# Container start: make sure the schema exists, then serve.
#
# There is no migration tool here — one `create_all`, which is a no-op on the
# second start. It runs in the container rather than as a deploy step so that
# bringing the stack up on an empty volume is the whole install; compose waits
# for Postgres to be healthy, so this cannot race the database.
set -e

invoicepilot migrate

exec uvicorn invoicepilot.app:api --host 0.0.0.0 --port 8000
