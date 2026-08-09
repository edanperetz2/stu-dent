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

echo
echo "Stu-Dent is up:"
echo "  Frontend:      http://localhost:5173"
echo "  API docs:      http://localhost:8000/docs"
echo "  MailHog:       http://localhost:8025"
echo
echo "One-time step: pull the local AI model (not baked into the ollama/ollama image):"
echo "  docker compose exec ollama ollama pull llama3.2"
echo
echo "Optional: seed demo data (idempotent, safe to re-run):"
echo "  docker compose exec api python -m app.seed_demo"
