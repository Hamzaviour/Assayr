setup() {
  load helpers
  command -v docker >/dev/null 2>&1 || skip "the docker CLI isn't installed"
  ENV_FILE="$BATS_TEST_TMPDIR/test.env"
  printf 'ASSAYR_VERSION=1.2.3\nPOSTGRES_PASSWORD=unused\nASSAYR_HTTPS_PORT=443\nASSAYR_HTTP_PORT=80\n' >"$ENV_FILE"
}

compose_config() {
  docker compose --env-file "$ENV_FILE" --project-directory "$REPO_ROOT/deploy" "$@" config
}

@test "the production compose file runs versioned images and builds nothing" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" == *"image: assayr-api:1.2.3"* ]]
  [[ "$output" == *"image: assayr-web:1.2.3"* ]]
  [[ "$output" == *"image: postgres:16-alpine"* ]]
  [[ "$output" != *"build:"* ]]
}

@test "every service has a health check, because up --wait refuses services without one" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" != *"disable: true"* ]]
  [[ "$output" == *"kill -0 1"* ]]
}

@test "malware scanning is an optional profile with a pinned image" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml" --profile av
  [ "$status" -eq 0 ]
  [[ "$output" == *"image: clamav/clamav-debian:1.4"* ]]
}

@test "the HTTPS override serves TLS on the HTTPS port with the certificates mounted" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml" -f "$REPO_ROOT/deploy/compose.https.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" == *"/etc/caddy/Caddyfile.https"* ]]
  [[ "$output" == *"target: 8443"* ]]
  [[ "$output" == *'published: "443"'* ]]
  [[ "$output" == *"target: /certs"* ]]
}

@test "the build override builds the images from source" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml" -f "$REPO_ROOT/deploy/compose.build.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" == *"context: "*"backend"* ]]
  [[ "$output" == *"context: "*"frontend"* ]]
}

@test "both Caddy configurations are valid" {
  docker info >/dev/null 2>&1 || skip "Docker isn't running"
  command -v openssl >/dev/null 2>&1 || skip "openssl isn't installed"
  local certs="$BATS_TEST_TMPDIR/certs" frontend="$REPO_ROOT/frontend" file
  mkdir -p "$certs"
  local subject=/CN=localhost
  if on_windows; then subject=//CN=localhost; fi # Git Bash would turn /CN=... into a Windows path
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "$subject" \
    -keyout "$certs/tls.key" -out "$certs/tls.crt" >/dev/null 2>&1
  if on_windows; then
    export MSYS_NO_PATHCONV=1
    certs="$(cygpath -m "$certs")"
    frontend="$(cygpath -m "$frontend")"
  fi
  for file in Caddyfile Caddyfile.https; do
    run docker run --rm -v "$frontend:/etc/caddy:ro" -v "$certs:/certs:ro" caddy:2-alpine \
      caddy validate --config "/etc/caddy/$file" --adapter caddyfile
    [ "$status" -eq 0 ] || { echo "$file: $output"; return 1; }
  done
}
