#!/usr/bin/env bash
# Short, memorable wrappers around the day-to-day docker compose commands
# documented in full in README.md. Run without arguments to see this list.
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  cat <<'EOF'
Usage: ./dev.sh <command>

  up              docker compose up --build -d
  down            docker compose down
  logs [service]  docker compose logs -f [service]
  test            run the backend pytest suite
  lint            ruff check, black --check, then npm run lint
  migrate <msg>   generate an Alembic revision from model changes, then apply it
  seed            seed idempotent demo data (safe to re-run)
EOF
}

cmd="${1:-}"
shift || true

case "$cmd" in
  up)
    docker compose up --build -d
    ;;
  down)
    docker compose down
    ;;
  logs)
    docker compose logs -f "$@"
    ;;
  test)
    docker compose exec api pytest -v
    ;;
  lint)
    docker compose exec api ruff check .
    docker compose exec api black --check .
    docker compose exec frontend npm run lint
    ;;
  migrate)
    msg="${1:-}"
    if [ -z "$msg" ]; then
      echo "Usage: ./dev.sh migrate \"describe the change\"" >&2
      exit 1
    fi
    docker compose exec api alembic revision --autogenerate -m "$msg"
    docker compose exec api alembic upgrade head
    ;;
  seed)
    docker compose exec api python -m app.seed_demo
    ;;
  *)
    usage
    exit 1
    ;;
esac
