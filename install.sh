#!/usr/bin/env bash
# One-command local install/run. Equivalent to the manual steps in README.md's
# "First run" section -- delegates the actual startup to dev.sh (the single
# definition of "how to start the stack," incl. the .env bootstrap), then
# adds waiting for everything to actually be ready before printing the URLs.
set -euo pipefail
cd "$(dirname "$0")"

./dev.sh up

echo "Waiting for the API to become healthy..."
api_container="$(docker compose ps -q api)"
for _ in $(seq 1 60); do
  status="$(docker inspect --format='{{.State.Health.Status}}' "$api_container" 2>/dev/null || echo starting)"
  if [ "$status" = "healthy" ]; then
    break
  fi
  sleep 2
done

echo "Waiting for the local AI model to finish pulling (one-time, cached after this)..."
docker compose wait ollama-init >/dev/null 2>&1 || true

echo "Waiting for demo data to finish seeding (skip by setting SEED_DEMO_ON_START=false in .env)..."
docker compose wait seed-init >/dev/null 2>&1 || true

echo
echo "Stu-Dent is up:"
echo "  Frontend:      http://localhost:5173"
echo "  API docs:      http://localhost:8000/docs"
echo "  MailHog:       http://localhost:8025"
