#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <image-repo> [tag]" >&2
  echo "Example: $0 ghcr.io/septem1997/graphiti-rest 0.28.2-episodes-v1" >&2
  exit 1
fi

IMAGE_REPO="$1"
IMAGE_TAG="${2:-0.28.2-episodes-v1}"
IMAGE_REF="${IMAGE_REPO}:${IMAGE_TAG}"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
VCS_REF="$(git rev-parse --short HEAD)"

echo "Building ${IMAGE_REF}"
docker build \
  --build-arg GRAPHITI_VERSION=0.28.2 \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${IMAGE_REF}" \
  .

echo "Pushing ${IMAGE_REF}"
docker push "${IMAGE_REF}"

echo
echo "Published image:"
echo "  ${IMAGE_REF}"
echo
echo "Next step for ops:"
echo "  cp deploy/graphiti-rest.env.example deploy/graphiti-rest.env"
echo "  edit deploy/graphiti-rest.env"
echo "  docker compose --env-file deploy/graphiti-rest.env -f deploy/docker-compose.graphiti-rest.yml up -d"
