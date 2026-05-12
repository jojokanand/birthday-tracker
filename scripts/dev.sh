#!/usr/bin/env bash
# Convenience script to spin up local dev servers.
# Backend on :8000, frontend on :3000 (once issue #6 lands).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/backend"
uv run uvicorn birthday_tracker.main:app --reload --port 8000
