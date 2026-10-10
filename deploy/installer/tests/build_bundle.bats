setup() {
  load helpers
  load_libs
  use_docker_stub
  OUT="$BATS_TEST_TMPDIR/dist"
}

@test "a bundle holds the installer, the compose files, the images and checksums" {
  STUB_IMAGES_PRESENT="$(stub_images 1.2.3)" run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 amd64 "$OUT" --no-archive
  [ "$status" -eq 0 ]
  local b="$OUT/assayr-1.2.3" f
  for f in assayr lib/main.sh lib/common.sh compose.yaml compose.https.yaml assayr.env.example \
    README-INSTALL.md VERSION ARCH SHA256SUMS images/IMAGES.txt; do
    [ -e "$b/$f" ] || { echo "missing $f"; return 1; }
  done
  [ "$(cat "$b/VERSION")" = 1.2.3 ]
  [ "$(cat "$b/ARCH")" = amd64 ]
  [ ! -e "$b/compose.build.yaml" ]
  [ "$(grep -c . "$b/images/IMAGES.txt")" -eq 4 ]
  grep -q "^assayr-api_1.2.3.tar assayr-api:1.2.3 sha256:" "$b/images/IMAGES.txt"
  grep -q "^clamav_clamav_1.4.tar clamav/clamav:1.4 sha256:" "$b/images/IMAGES.txt"
  [ -f "$b/images/postgres_16-alpine.tar" ]
  run verify_bundle "$b"
  [ "$status" -eq 0 ]
}

@test "the archive unpacks to the bundle folder" {
  STUB_IMAGES_PRESENT="$(stub_images 1.2.3)" run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 arm64 "$OUT"
  [ "$status" -eq 0 ]
  [ -f "$OUT/assayr-1.2.3-linux-arm64-offline.tar.gz" ]
  run tar -tzf "$OUT/assayr-1.2.3-linux-arm64-offline.tar.gz"
  [[ "$output" == *"assayr-1.2.3/assayr"* ]]
  [[ "$output" == *"assayr-1.2.3/SHA256SUMS"* ]]
}

@test "a bundle can't be built without the Assayr images" {
  STUB_IMAGES_PRESENT="assayr-web:1.2.3 postgres:16-alpine clamav/clamav:1.4" \
    run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 amd64 "$OUT" --no-archive
  [ "$status" -eq 1 ]
  [[ "$output" == *"Image assayr-api:1.2.3 is missing; build it first."* ]]
}

@test "the version and architecture are checked" {
  run "$REPO_ROOT/scripts/build-bundle.sh" v1.2.3 amd64 "$OUT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Give a version like 0.2.0"* ]]
  run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 x86 "$OUT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ARCH must be amd64 or arm64"* ]]
}

@test "load_images loads only the images that aren't there yet" {
  local b
  b="$(make_bundle 1.2.3 "$OUT")"
  : >"$STUB_LOG"
  STUB_IMAGES_PRESENT="postgres:16-alpine" run load_images "$b"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Image postgres:16-alpine is already loaded"* ]]
  [ "$(grep -c "^load -i " "$STUB_LOG")" -eq 3 ]
  grep -qF "load -i $b/images/assayr-api_1.2.3.tar" "$STUB_LOG"
}
