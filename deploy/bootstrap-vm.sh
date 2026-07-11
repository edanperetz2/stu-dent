#!/usr/bin/env bash
# First-time setup for the course-supplied VM. Idempotent -- safe to
# re-run. Written for a Debian/Ubuntu VM with sudo access (the most
# common shape for a course-supplied VM); adjust if the real VM turns out
# to be something else.
set -euo pipefail

if ! command -v docker &> /dev/null; then
  echo "Docker not found -- installing via Docker's official convenience script..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. Log out and back in (or run 'newgrp docker') for the group change to take effect."
else
  echo "Docker already installed, skipping."
fi

if command -v ufw &> /dev/null && sudo ufw status | grep -q "Status: active"; then
  echo "ufw is active -- opening ports 22 (ssh), 80 (frontend), 8000 (api), 8025 (mailhog UI)..."
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 8000/tcp
  sudo ufw allow 8025/tcp
else
  echo "ufw not active/installed -- skipping firewall rules (this VM likely manages exposure at the network level instead)."
fi

cat <<'EOF'

Bootstrap done. Next steps:
  1. git clone https://github.com/edanperetz2/stu-dent.git && cd stu-dent
  2. cp .env.example .env
  3. Edit .env: set VITE_API_URL to this VM's real address (e.g.
     http://<vm-ip>:8000), set FRONTEND_ORIGINS to include this VM's
     frontend URL (e.g. http://<vm-ip>), and generate a real JWT_SECRET_KEY.
  4. docker compose -f docker-compose.prod.yml up -d --build
  5. (optional, one-time) pull the Ollama model:
     docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2
EOF
