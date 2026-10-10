setup() {
  load helpers
  load_libs
  use_docker_stub
}

@test "a stopped Docker is reported with how to start it on that platform" {
  STUB_NO_DAEMON=1 run check_docker wsl
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker is installed but not running"* ]]
  [[ "$output" == *"WSL integration"* ]]
}

@test "a machine without Docker is told where to get it" {
  PATH="$BATS_TEST_TMPDIR/empty" run check_docker linux
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker is not installed."* ]]
  [[ "$output" == *"docs.docker.com/engine/install"* ]]
}

@test "Compose must be 2.17 or newer, including Docker Desktop's version strings" {
  STUB_COMPOSE_VERSION=2.12.0 run check_docker linux
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker Compose 2.12.0 is too old"* ]]
  STUB_COMPOSE_VERSION=v2.29.2-desktop.2 run check_docker macos
  [ "$status" -eq 0 ]
}

@test "a bundle for another architecture is refused with the right download named" {
  STUB_ARCH=aarch64 run check_arch amd64
  [ "$status" -eq 1 ]
  [[ "$output" == *"This bundle is for amd64 but this machine is arm64."* ]]
  [[ "$output" == *"linux-arm64-offline.tar.gz"* ]]
  STUB_ARCH=x86_64 run check_arch amd64
  [ "$status" -eq 0 ]
}

@test "not enough free disk space is refused" {
  ASSAYR_MIN_FREE_GB=100000000 run check_disk "$BATS_TEST_TMPDIR/not/created/yet"
  [ "$status" -eq 1 ]
  [[ "$output" == *"At least 100000000 GB of free disk space is needed"* ]]
}

@test "less than 4 GB of Docker memory is a warning, not an error" {
  STUB_MEM=2147483648 run check_memory
  [ "$status" -eq 0 ]
  [[ "$output" == *"less than 4 GB of memory"* ]]
}

@test "a port in use is refused with the option to choose another" {
  port_in_use() { return 0; }
  run check_port 443 --https-port
  [ "$status" -eq 1 ]
  [[ "$output" == *"Port 443 is already in use. Free it or choose another port with --https-port."* ]]
}

@test "assayr_compose adds the HTTPS file and the malware-scanning profile from the settings" {
  ASSAYR_DIR="$BATS_TEST_TMPDIR/my install"
  mkdir -p "$ASSAYR_DIR"
  printf 'ASSAYR_WEB_MODE=https\nASSAYR_MALWARE_SCAN=true\n' >"$ASSAYR_DIR/assayr.env"
  assayr_compose ps
  grep -qF -- "--project-directory $ASSAYR_DIR --env-file $ASSAYR_DIR/assayr.env -f $ASSAYR_DIR/compose.yaml -f $ASSAYR_DIR/compose.https.yaml --profile av ps" "$STUB_LOG"
  : >"$STUB_LOG"
  printf 'ASSAYR_WEB_MODE=http\nASSAYR_MALWARE_SCAN=false\n' >"$ASSAYR_DIR/assayr.env"
  assayr_compose ps
  run grep -c -e compose.https.yaml -e "--profile av" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "install_url leaves out the standard ports" {
  ASSAYR_DIR="$BATS_TEST_TMPDIR"
  printf 'ASSAYR_HOSTNAME=grc.local\nASSAYR_WEB_MODE=https\nASSAYR_HTTPS_PORT=443\n' >"$ASSAYR_DIR/assayr.env"
  [ "$(install_url)" = https://grc.local ]
  printf 'ASSAYR_HOSTNAME=grc.local\nASSAYR_WEB_MODE=https\nASSAYR_HTTPS_PORT=8443\n' >"$ASSAYR_DIR/assayr.env"
  [ "$(install_url)" = https://grc.local:8443 ]
  printf 'ASSAYR_HOSTNAME=grc.local\nASSAYR_WEB_MODE=http\nASSAYR_HTTP_PORT=8080\n' >"$ASSAYR_DIR/assayr.env"
  [ "$(install_url)" = http://grc.local:8080 ]
}

@test "create_admin_account passes the password by environment name only" {
  ASSAYR_DIR="$BATS_TEST_TMPDIR"
  printf 'ASSAYR_WEB_MODE=https\n' >"$ASSAYR_DIR/assayr.env"
  create_admin_account admin@example.com "secret-password-123"
  grep -qF -- "exec -T -e ASSAYR_ADMIN_PASSWORD api assayr create-admin --email admin@example.com" "$STUB_LOG"
  run grep -c "secret-password-123" "$STUB_LOG"
  [ "$output" = 0 ]
}
