setup() {
  load helpers
  load_libs
  use_docker_stub
  BUNDLE="$(make_bundle 1.2.3 "$BATS_TEST_TMPDIR/dist")"
  DIR="$BATS_TEST_TMPDIR/install"
  : >"$STUB_LOG"
}

@test "install writes the settings and a certificate, starts Assayr and creates the administrator" {
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 0 ]
  local env="$DIR/assayr.env"
  [ "$(env_get ASSAYR_VERSION "$env")" = 1.2.3 ]
  [ "$(env_get ASSAYR_WEB_MODE "$env")" = https ]
  [ "$(env_get ASSAYR_HTTPS_PORT "$env")" = 18443 ]
  [ "$(env_get ASSAYR_HTTP_PORT "$env")" = 18080 ]
  [ "$(env_get ASSAYR_SECURE_COOKIES "$env")" = true ]
  [ "$(env_get ASSAYR_ORG_NAME "$env")" = "Test Org" ]
  [ "$(env_get ASSAYR_CLAMAV_HOST "$env")" = clamav ]
  [[ "$(env_get POSTGRES_PASSWORD "$env")" =~ ^[A-Za-z0-9]{32}$ ]]
  [ -f "$DIR/certs/tls.crt" ] && [ -f "$DIR/certs/tls.key" ]
  [ "$(cat "$DIR/VERSION")" = 1.2.3 ]
  [ -x "$DIR/assayr" ] || on_windows
  grep -q "up -d --wait --wait-timeout 600" "$STUB_LOG"
  grep -q "create-admin --email admin@example.com" "$STUB_LOG"
  [[ "$output" == *"Assayr 1.2.3 is running."* ]]
  [[ "$output" == *"Address:        https://localhost:18443"* ]]
  [[ "$output" == *"self-signed, SHA-256 fingerprint"* ]]
}

@test "the administrator password never reaches a command line, the log or the screen" {
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 0 ]
  run grep -c "test-password-123" "$STUB_LOG" "$DIR/install.log"
  [[ "$output" == *"docker.log:0"* ]]
  [[ "$output" == *"install.log:0"* ]]
}

@test "settings, keys and the log are readable by the owner only" {
  skip_on_windows
  install_fixture "$BUNDLE" "$DIR"
  [ "$(file_mode "$DIR/assayr.env")" = "rw-------" ]
  [ "$(file_mode "$DIR/certs/tls.key")" = "rw-------" ]
  [ "$(file_mode "$DIR/install.log")" = "rw-------" ]
  [ "$(file_mode "$DIR/backups")" = "rwx------" ]
}

@test "install refuses to run over an existing installation" {
  install_fixture "$BUNDLE" "$DIR"
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr is already installed in $DIR."* ]]
  [[ "$output" == *"./assayr upgrade"* ]]
}

@test "install refuses an organisation name that would break the settings file" {
  ASSAYR_ORG_NAME='Acme $HOME' run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Organisation name can't contain"* ]]
  [ ! -e "$DIR" ]
}

@test "install without an administrator email fails when running without questions" {
  ASSAYR_ADMIN_EMAIL="" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Set ASSAYR_ADMIN_EMAIL when using --non-interactive."* ]]
}

@test "--http serves plain HTTP with secure cookies off, unless a proxy adds HTTPS" {
  run install_fixture "$BUNDLE" "$DIR" --http
  [ "$status" -eq 0 ]
  [ "$(env_get ASSAYR_WEB_MODE "$DIR/assayr.env")" = http ]
  [ "$(env_get ASSAYR_SECURE_COOKIES "$DIR/assayr.env")" = false ]
  [ ! -e "$DIR/certs/tls.crt" ]
  [[ "$output" == *"plain HTTP"* ]]
  [[ "$output" == *"http://localhost:18080"* ]]
  run grep -c compose.https.yaml "$STUB_LOG"
  [ "$output" = 0 ]

  local proxied="$BATS_TEST_TMPDIR/proxied"
  ASSAYR_BEHIND_TLS_PROXY=yes run install_fixture "$BUNDLE" "$proxied" --http
  [ "$status" -eq 0 ]
  [ "$(env_get ASSAYR_SECURE_COOKIES "$proxied/assayr.env")" = true ]
}

@test "install works in a folder whose path has spaces" {
  local spaced="$BATS_TEST_TMPDIR/my apps/assayr"
  run install_fixture "$BUNDLE" "$spaced"
  [ "$status" -eq 0 ]
  [ -f "$spaced/assayr.env" ]
  grep -qF -- "--project-directory $spaced " "$STUB_LOG"
}

@test "a modified bundle is refused before anything is written" {
  echo "# changed" >>"$BUNDLE/compose.yaml"
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"This bundle is damaged or was modified: ./compose.yaml does not match its checksum."* ]]
  [ ! -e "$DIR" ]
}

@test "a bundle for another architecture is refused" {
  STUB_ARCH=aarch64 run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"this machine is arm64"* ]]
}

@test "a licence file is copied in for the application" {
  echo "licence-data" >"$BATS_TEST_TMPDIR/acme.lic"
  run install_fixture "$BUNDLE" "$DIR" --license "$BATS_TEST_TMPDIR/acme.lic"
  [ "$status" -eq 0 ]
  [ "$(cat "$DIR/license/assayr.lic")" = licence-data ]
}

@test "images that aren't loaded yet are loaded from the bundle" {
  STUB_IMAGES_PRESENT="" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 0 ]
  [ "$(grep -c "^load -i " "$STUB_LOG")" -eq 4 ]
}

@test "when Assayr doesn't start, install says how to start again" {
  STUB_FAIL_ON="--wait-timeout" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr did not start."* ]]
  [[ "$output" == *"uninstall --delete-data, then run install again."* ]]
}

@test "on Linux install needs root" {
  ASSAYR_EUID=1000 run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"sudo ./assayr install"* ]]
}

@test "on macOS it installs in the home folder and says it is for evaluation" {
  export HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$HOME"
  ASSAYR_UNAME_S=Darwin ASSAYR_EUID=501 ASSAYR_HOSTNAME=localhost ASSAYR_ORG_NAME="Test Org" \
    ASSAYR_ADMIN_EMAIL=admin@example.com ASSAYR_ADMIN_PASSWORD=test-password-123 \
    STUB_IMAGES_PRESENT="$(stub_images 1.2.3)" \
    run "$BUNDLE/assayr" install --non-interactive --https-port 18443 --http-port 18080
  [ "$status" -eq 0 ]
  [ -f "$HOME/assayr/assayr.env" ]
  [[ "$output" == *"for evaluation"* ]]
}

@test "install refuses when Docker already holds another Assayr installation's data or containers" {
  STUB_VOLUMES_PRESENT=assayr_dbdata run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker on this machine already has an Assayr installation"* ]]
  [ ! -e "$DIR" ]
  run grep -c -- "up -d" "$STUB_LOG"
  [ "$output" = 0 ]
  STUB_CONTAINERS="0123abcd" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"already has an Assayr installation"* ]]
}

@test "install refuses a folder that already holds other files" {
  mkdir -p "$DIR"
  echo "someone else's file" >"$DIR/notes.txt"
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"$DIR isn't empty."* ]]
  [ ! -e "$DIR/assayr.env" ]
}
