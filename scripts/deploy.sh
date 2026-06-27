#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env.local"

if [[ -f "$ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
fi

if [[ -z "${DEPLOY_HOST:-}" ]]; then
    echo "Error: DEPLOY_HOST is not set. Define it in .env.local or export it before running." >&2
    exit 1
fi

echo "Deploying to $DEPLOY_HOST..."
ssh "$DEPLOY_HOST" "/volume3/docker/sc-discord-bot/scripts/run.sh"
