#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="csd:latest"
CLUSTER_NAME="dev"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE_PATH="${SCRIPT_DIR}/Dockerfile"
BUILD_CONTEXT="${SCRIPT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker not found in PATH" >&2
  exit 1
fi

if ! command -v k3d >/dev/null 2>&1; then
  echo "Error: k3d not found in PATH" >&2
  exit 1
fi

if ! k3d cluster list --no-headers 2>/dev/null | awk '{print $1}' | grep -qx "${CLUSTER_NAME}"; then
  echo "Error: k3d cluster '${CLUSTER_NAME}' not found" >&2
  exit 1
fi

echo "[1/2] Building image ${IMAGE_TAG} ..."
docker build -t "${IMAGE_TAG}" -f "${DOCKERFILE_PATH}" "${BUILD_CONTEXT}"

echo "[2/2] Importing image ${IMAGE_TAG} into k3d cluster ${CLUSTER_NAME} ..."
k3d image import "${IMAGE_TAG}" -c "${CLUSTER_NAME}"

echo "Done. Image '${IMAGE_TAG}' is available in cluster '${CLUSTER_NAME}'."
