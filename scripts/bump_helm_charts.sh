#!/usr/bin/env bash
# Bump local Helm chart patch versions and prod image tags after a CI image publish.
# Usage:
#   IMAGE_TAG=sha-abc1234 ./scripts/bump_helm_charts.sh
#   IMAGE_REGISTRY=ghcr.io/org/repo IMAGE_TAG=sha-abc1234 ./scripts/bump_helm_charts.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Empty registry = local names from GitHub Actions artifacts (keep-backend:sha-xxx).
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:?set IMAGE_TAG}"

image_repo() {
  local name="$1"
  if [ -n "$IMAGE_REGISTRY" ]; then
    echo "${IMAGE_REGISTRY}/${name}"
  else
    echo "${name}"
  fi
}

bump_patch() {
  local file="$1"
  python3 - "$file" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path).read()

def inc(match):
    major, minor, patch = (int(p) for p in match.group(2).split("."))
    return f"{match.group(1)}{major}.{minor}.{patch + 1}"

new, n = re.subn(r"(?m)^(version:\s*)(\d+\.\d+\.\d+)", inc, text, count=1)
if n != 1:
    raise SystemExit(f"could not bump version in {path}")
open(path, "w").write(new)
print(f"bumped {path}")
PY
}

set_image() {
  local file="$1"
  local repo="$2"
  python3 - "$file" "$repo" "$IMAGE_TAG" <<'PY'
import re, sys
path, repo, tag = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path).read()
text, n1 = re.subn(r"(?m)^(\s*repository:\s*).+$", rf"\1{repo}", text, count=1)
text, n2 = re.subn(r"(?m)^(\s*tag:\s*).+$", rf'\1"{tag}"', text, count=1)
if n1 < 1 or n2 < 1:
    raise SystemExit(f"could not set image in {path} (repo={n1} tag={n2})")
open(path, "w").write(text)
print(f"set {path} → {repo}:{tag}")
PY
}

set_keep_prod_image() {
  local component="$1"
  local repo="$2"
  python3 - "$ROOT/helm/keep-values-prod.yaml" "$component" "$repo" "$IMAGE_TAG" <<'PY'
import sys
from pathlib import Path
path, component, repo, tag = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
lines = path.read_text().splitlines(keepends=True)
out = []
in_block = False
replaced_repo = replaced_tag = False
for line in lines:
    if line.startswith(f"{component}:"):
        in_block = True
        out.append(line)
        continue
    if in_block and line and not line[0].isspace() and not line.startswith("#"):
        in_block = False
    if in_block and not replaced_repo and line.strip().startswith("repository:"):
        indent = line[: len(line) - len(line.lstrip())]
        out.append(f"{indent}repository: {repo}\n")
        replaced_repo = True
        continue
    if in_block and not replaced_tag and line.strip().startswith("tag:"):
        indent = line[: len(line) - len(line.lstrip())]
        out.append(f'{indent}tag: "{tag}"\n')
        replaced_tag = True
        continue
    out.append(line)
if not (replaced_repo and replaced_tag):
    raise SystemExit(f"could not update {component} image in {path}")
path.write_text("".join(out))
print(f"set keep-values-prod {component} → {repo}:{tag}")
PY
}

cd "$ROOT"

for chart in helm/temporal-worker helm/provider-mock helm/temporal helm/synthetic-checks; do
  bump_patch "${chart}/Chart.yaml"
done

set_image helm/temporal-worker/values-prod.yaml "$(image_repo keep-temporal-worker)"
set_image helm/provider-mock/values-prod.yaml "$(image_repo keep-provider-mock)"
set_keep_prod_image backend "$(image_repo keep-backend)"
set_keep_prod_image frontend "$(image_repo keep-frontend)"

echo "Helm charts bumped for ${IMAGE_REGISTRY:-local} tag=${IMAGE_TAG}"
