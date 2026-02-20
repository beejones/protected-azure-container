#!/bin/bash
# Build and push a Docker image to a registry.
# Usage: ./scripts/deploy/build_push.sh [tag]  (default: latest)
#
# Reads from env or .env.deploy:
#   REGISTRY     e.g. ghcr.io
#   IMAGE_NAME   e.g. beejones/my-app
#   DOCKERFILE   e.g. docker/Dockerfile (default)

set -euo pipefail

if [ -f .env.deploy ]; then
  set -a
  # shellcheck disable=SC1091
  . .env.deploy
  set +a
fi

REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME must be set}"
DOCKERFILE="${DOCKERFILE:-docker/Dockerfile}"
TAG="${1:-latest}"
FULL_IMAGE="$REGISTRY/$IMAGE_NAME:$TAG"

echo "[build-push] Building $FULL_IMAGE..."
docker build -f "$DOCKERFILE" -t "$FULL_IMAGE" .

echo "[build-push] Pushing $FULL_IMAGE..."
docker push "$FULL_IMAGE"

echo "[build-push] Done."
