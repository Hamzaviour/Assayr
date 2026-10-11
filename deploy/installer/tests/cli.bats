setup() {
  load helpers
  load_libs
  use_docker_stub
  OUT="$BATS_TEST_TMPDIR/dist"
}

@test "help lists the commands" {
  run "$INSTALLER/assayr" help
  [ "$status" -eq 0 ]
  local command
  for command in install upgrade status backup restore start stop restart logs create-admin uninstall version; do
    [[ "$output" == *"  $command"* ]] || { echo "help misses $command"; return 1; }
  done
}

@test "an unknown command is refused" {
  run "$INSTALLER/assayr" frobnicate
  [ "$status" -eq 1 ]
  [[ "$output" == *"Unknown command: frobnicate"* ]]
}

@test "install must run from an unpacked bundle" {
  run "$INSTALLER/assayr" install
  [ "$status" -eq 1 ]
  [[ "$output" == *"Run install from an unpacked bundle"* ]]
}

@test "version reports the bundle's version and architecture" {
  local b
  b="$(make_bundle 1.2.3 "$OUT")"
  run "$b/assayr" version
  [ "$status" -eq 0 ]
  [ "$output" = "Assayr 1.2.3 (amd64)" ]
}

@test "installation commands say where they looked when nothing is installed" {
  run "$INSTALLER/assayr" status --dir "$BATS_TEST_TMPDIR/nothing here"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No Assayr installation found in $BATS_TEST_TMPDIR/nothing here."* ]]
}

@test "installation commands on Linux need root" {
  ASSAYR_EUID=1000 run "$INSTALLER/assayr" status
  [ "$status" -eq 1 ]
  [[ "$output" == *"sudo ./assayr status"* ]]
}

@test "status shows the version, the address and whether the application is ready" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  run "$dir/assayr" status
  [ "$status" -eq 0 ]
  [[ "$output" == *"Assayr 1.2.3 (amd64) in $dir"* ]]
  [[ "$output" == *"Address: https://localhost:18443"* ]]
  [[ "$output" == *"Application: ready"* ]]
}

@test "stop, start and restart drive the stack" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  : >"$STUB_LOG"
  run "$dir/assayr" restart
  [ "$status" -eq 0 ]
  grep -q " stop$" "$STUB_LOG"
  grep -q "up -d --wait --wait-timeout 600$" "$STUB_LOG"
  [[ "$output" == *"Assayr is running at https://localhost:18443"* ]]
}

@test "create-admin creates another administrator without exposing the password" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  : >"$STUB_LOG"
  ASSAYR_ADMIN_EMAIL=second@example.com ASSAYR_ADMIN_PASSWORD=another-password-456 \
    run "$dir/assayr" create-admin --non-interactive
  [ "$status" -eq 0 ]
  grep -q "create-admin --email second@example.com" "$STUB_LOG"
  run grep -c "another-password-456" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "uninstall keeps the data unless asked to delete it, and deleting needs confirmation" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  : >"$STUB_LOG"
  run "$dir/assayr" uninstall
  [ "$status" -eq 0 ]
  grep -q "down --remove-orphans$" "$STUB_LOG"
  [ -f "$dir/assayr.env" ]

  run "$dir/assayr" uninstall --delete-data </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"Cancelled; nothing was changed."* ]]
  [ -f "$dir/assayr.env" ]

  run "$dir/assayr" uninstall --delete-data --yes
  [ "$status" -eq 0 ]
  grep -q "down -v --remove-orphans$" "$STUB_LOG"
  grep -q "image rm assayr-api:1.2.3 assayr-web:1.2.3" "$STUB_LOG"
  [ ! -e "$dir" ]
}

@test "uninstall --delete-data removes only what the installer created" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  echo "added later by someone" >"$dir/notes.txt"
  run "$dir/assayr" uninstall --delete-data --yes
  [ "$status" -eq 0 ]
  [ -f "$dir/notes.txt" ]
  [ ! -e "$dir/assayr.env" ] && [ ! -e "$dir/lib" ] && [ ! -e "$dir/backups" ] && [ ! -e "$dir/certs" ]
  [[ "$output" == *"$dir still holds files Assayr didn't create"* ]]
}
