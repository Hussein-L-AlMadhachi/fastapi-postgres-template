#!/usr/bin/env bash
set -euo pipefail

if ! grep -q '^APP_SECRET=' .env 2>/dev/null; then
    echo "APP_SECRET is missing from .env. Generate one with: openssl rand -hex 32" >&2
    exit 1
fi

podman compose up --build --force-recreate
