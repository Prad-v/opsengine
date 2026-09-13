#!/usr/bin/env bash
# Package Helm charts (and optionally docker-save images) for GitHub Actions artifacts.
# Usage:
#   ./scripts/package_ci_artifacts.sh
#   SAVE_IMAGES=1 IMAGE_TAG=sha-abc1234 ./scripts/package_ci_artifacts.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ARTIFACT_DIR:-$ROOT/dist/ci-artifacts}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
HELM_IMAGE="${HELM_IMAGE:-alpine/helm:3.16.4}"

CHARTS=(
  helm/temporal
  helm/temporal-worker
  helm/provider-mock
  helm/synthetic-checks
)

IMAGES=(
  "keep-backend:${IMAGE_TAG}"
  "keep-frontend:${IMAGE_TAG}"
  "keep-temporal-worker:${IMAGE_TAG}"
  "keep-provider-mock:${IMAGE_TAG}"
)

mkdir -p "$OUT/charts" "$OUT/images"

echo "Packaging Helm charts → $OUT/charts"
docker run --rm \
  -v "$ROOT:/work:ro" \
  -v "$OUT/charts:/out" \
  -w /work \
  "$HELM_IMAGE" \
  sh -c '
    set -eu
    for chart in '"${CHARTS[*]}"'; do
      helm lint "$chart"
      helm package "$chart" --destination /out
    done
    helm repo index /out
  '

if [ "${SAVE_IMAGES:-0}" = "1" ]; then
  echo "Saving Docker images → $OUT/images"
  for image in "${IMAGES[@]}"; do
    name="$(echo "$image" | tr '/:' '__')"
    if ! docker image inspect "$image" >/dev/null 2>&1; then
      echo "skip missing image: $image" >&2
      continue
    fi
    docker save "$image" | gzip -1 > "$OUT/images/${name}.tar.gz"
    echo "saved $image"
  done
fi

cat > "$OUT/manifest.txt" <<EOF
image_tag=${IMAGE_TAG}
git_sha=${GITHUB_SHA:-unknown}
charts=$(ls -1 "$OUT/charts"/*.tgz 2>/dev/null | xargs -n1 basename | tr '\n' ' ')
images=$(ls -1 "$OUT/images"/*.tar.gz 2>/dev/null | xargs -n1 basename | tr '\n' ' ')
EOF

echo "CI artifacts ready in $OUT"
cat "$OUT/manifest.txt"
