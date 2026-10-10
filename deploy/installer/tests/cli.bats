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
