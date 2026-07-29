#!/bin/sh
set -e

python -m app.migrate_with_lock

exec "$@"
