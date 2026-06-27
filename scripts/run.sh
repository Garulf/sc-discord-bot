#!/bin/sh
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# Determine whether docker needs sudo
DOCKER="docker"
if ! docker info > /dev/null 2>&1; then
    if sudo docker info > /dev/null 2>&1; then
        DOCKER="sudo docker"
    else
        echo "Error: cannot connect to Docker daemon (tried with and without sudo)" >&2
        exit 1
    fi
fi

FORCE=0
for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
    esac
done

cd "$REPO_DIR"

# Record current commit before pulling
BEFORE="$(git rev-parse HEAD)"

echo "Pulling latest changes..."
git pull

AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ] && [ "$FORCE" = "0" ]; then
    echo "No new changes — skipping rebuild."
    exit 0
fi

if [ "$BEFORE" = "$AFTER" ]; then
    echo "No new changes — forcing rebuild anyway."
else
    echo "New commits detected ($BEFORE -> $AFTER), rebuilding..."
fi

# Use docker compose v2 (plugin) if available, fall back to v1 (standalone)
if $DOCKER compose version > /dev/null 2>&1; then
    COMPOSE="$DOCKER compose"
elif command -v docker-compose > /dev/null 2>&1; then
    if [ "$DOCKER" = "sudo docker" ]; then
        COMPOSE="sudo docker-compose"
    else
        COMPOSE="docker-compose"
    fi
else
    echo "Error: neither 'docker compose' nor 'docker-compose' found" >&2
    exit 1
fi

$COMPOSE build --pull
$COMPOSE up -d --force-recreate

echo "Done."
