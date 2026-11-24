#!/usr/bin/env bash
set -euo pipefail
# Setup development environment for frontend, backend, and alpha.

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

initialize_env_file() {
  local project="$1"
  if [[ ! -f "$project/.env" && -f "$project/.env.example" ]]; then
    cp "$project/.env.example" "$project/.env"
    echo "Created $project/.env from its example; review local settings."
  fi
}

for project in frontend backend alpha; do
  initialize_env_file "$project"
done

echo "Installing frontend dependencies..."
HUSKY=0 npm ci --prefix frontend
npm exec --prefix frontend -- husky install

echo "Installing backend dependencies..."
uv sync --project backend

echo "Installing alpha dependencies..."
uv sync --project alpha

echo "Setup complete."
echo "Frontend: cd frontend && npm run dev"
echo "Backend:  cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo "Alpha UI: cd alpha && uv run streamlit run app/streamlit_app.py --server.address 127.0.0.1"
echo "Alpha test: cd alpha && uv run test_local.py"
echo "Review each .env.example; local .env files are never overwritten."
