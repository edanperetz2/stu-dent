#!/usr/bin/env bash
# One-command local install/run. Equivalent to the manual steps in README.md's
# "First run" section -- this script just automates them.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose up --build -d

echo "Waiting for the API to become healthy..."
for _ in $(seq 1 60); do
  status="$(docker inspect --format='{{.State.Health.Status}}' finalproject-api-1 2>/dev/null || echo starting)"
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
