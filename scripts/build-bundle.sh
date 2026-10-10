#!/usr/bin/env bash
# Assemble an offline installer bundle from images on this machine.
# Usage: scripts/build-bundle.sh VERSION ARCH OUTDIR [--no-archive]
# Needs assayr-api:VERSION and assayr-web:VERSION built locally; pulls the third-party images
# listed in deploy/compose.yaml when they are missing.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../deploy/installer/lib/common.sh
. "$REPO/deploy/installer/lib/common.sh"
# shellcheck source=../deploy/installer/lib/bundle.sh
. "$REPO/deploy/installer/lib/bundle.sh"

version="${1:-}"
arch="${2:-}"
out="${3:-}"
archive=1
if [ "${4:-}" = --no-archive ]; then archive=0; fi
version_valid "$version" || die "Give a version like 0.2.0 (got '$version')."
case "$arch" in amd64 | arm64) ;; *) die "ARCH must be amd64 or arm64 (got '$arch')." ;; esac
[ -n "$out" ] || die "Give an output folder."

installer="$REPO/deploy/installer"
bundle="$out/assayr-$version"
rm -rf "$bundle"
mkdir -p "$bundle/images"
cp "$installer/assayr" "$installer/assayr.env.example" "$installer/README-INSTALL.md" "$bundle/"
cp -R "$installer/lib" "$bundle/lib"
cp "$REPO/deploy/compose.yaml" "$REPO/deploy/compose.https.yaml" "$bundle/"
chmod 755 "$bundle/assayr"
printf '%s\n' "$version" >"$bundle/VERSION"
printf '%s\n' "$arch" >"$bundle/ARCH"

images="$(ASSAYR_VERSION="$version" POSTGRES_PASSWORD=unused \
  docker compose -f "$bundle/compose.yaml" --profile av config --images | LC_ALL=C sort -u)"
: >"$bundle/images/IMAGES.txt"
# shellcheck disable=SC2086 # one image reference per word
for ref in $images; do
  case "$ref" in
    assayr-*) docker image inspect "$ref" >/dev/null 2>&1 || die "Image $ref is missing; build it first." ;;
    *) docker image inspect "$ref" >/dev/null 2>&1 || docker pull "$ref" >/dev/null ;;
  esac
  file="$(printf '%s' "$ref" | tr '/:' '__').tar"
  info "Saving $ref"
  docker save -o "$bundle/images/$file" "$ref"
  printf '%s %s %s\n' "$file" "$ref" "$(docker image inspect --format '{{.Id}}' "$ref")" >>"$bundle/images/IMAGES.txt"
done

write_sums "$bundle"
if [ "$archive" = 1 ]; then
  tarball="$out/assayr-$version-linux-$arch-offline.tar.gz"
  tar -C "$out" -czf "$tarball" "assayr-$version"
  info "Bundle written to $tarball"
else
  info "Bundle folder written to $bundle"
fi
