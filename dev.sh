#!/usr/bin/env bash
# Short, memorable wrappers around the day-to-day docker compose commands
# documented in full in README.md. Run without arguments to see this list.
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  cat <<'EOF'
Usage: ./dev.sh <command>

  up               docker compose up --build -d
  down             docker compose down
  logs [service]   docker compose logs -f [service]
  test             run the backend pytest suite
  test-frontend    run the frontend vitest suite
  lint             ruff check, black --check, then npm run lint
  migrate <msg>    generate an Alembic revision from model changes, then apply it
  seed             seed idempotent demo data (safe to re-run)
  update-deps      regenerate the hash-locked backend dependency files
  update-digests   re-pin every base/service image to its current digest
EOF
}

# Re-pins one image's @sha256:... digest everywhere it's referenced. Kept as
# a deliberate, explicit command (not run automatically on `up`/build) --
# the whole point of digest pinning is that builds do NOT change silently.
update_one_digest() {
  local image="$1"
  shift
  echo "Pulling $image..."
  docker pull "$image" >/dev/null
  local digest
  digest="$(docker inspect --format='{{index .RepoDigests 0}}' "$image" | grep -oE 'sha256:[a-f0-9]+' || true)"
  if [ -z "$digest" ]; then
    echo "  Could not resolve a digest for $image -- skipping" >&2
    return
  fi
  echo "  -> ${image}@${digest}"
  for file in "$@"; do
    sed -i -E "s#${image}@sha256:[a-f0-9]+#${image}@${digest}#g" "$file"
  done
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
  test-frontend)
    docker compose exec frontend npm run test
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
  update-deps)
    # MSYS_NO_PATHCONV: on Windows Git Bash, MSYS auto-rewrites any argument
    # that looks like a POSIX path, which mangles the container-side half of
    # -v/-w (e.g. /work becomes C:/Program Files/Git/work) -- harmless to set
    # on Mac/Linux where MSYS doesn't exist.
    MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD/backend:/work" -w /work python:3.12-slim bash -c "
      pip install --no-cache-dir pip-tools &&
      pip-compile requirements.txt --generate-hashes --output-file=requirements.lock.txt &&
      pip-compile requirements-dev.txt --generate-hashes --output-file=requirements-dev.lock.txt
    "
    echo
    echo "Done -- review with: git diff backend/requirements*.lock.txt"
    ;;
  update-digests)
    update_one_digest "python:3.12-slim" backend/Dockerfile
    update_one_digest "node:22-alpine" frontend/Dockerfile
    update_one_digest "postgres:16" docker-compose.yml .github/workflows/ci.yml
    update_one_digest "ollama/ollama" docker-compose.yml
    update_one_digest "mailhog/mailhog" docker-compose.yml
    echo
    echo "Done -- review with: git diff, then run ./dev.sh up to rebuild against the new images"
    ;;
  *)
    usage
    exit 1
    ;;
esac
