setup() {
  load helpers
  load_libs
  ENV_FILE="$BATS_TEST_TMPDIR/assayr.env"
}

@test "env_get returns the last value of a key, or nothing" {
  printf 'A=1\nB=two words\nA=3\n' >"$ENV_FILE"
  [ "$(env_get A "$ENV_FILE")" = 3 ]
  [ "$(env_get B "$ENV_FILE")" = "two words" ]
  [ -z "$(env_get MISSING "$ENV_FILE")" ]
  [ -z "$(env_get A "$BATS_TEST_TMPDIR/no-such-file")" ]
}

@test "env_set replaces a key, keeps the others and handles = in values" {
  printf 'A=1\nB=2\n' >"$ENV_FILE"
  env_set A "x=y z" "$ENV_FILE"
  [ "$(env_get A "$ENV_FILE")" = "x=y z" ]
  [ "$(env_get B "$ENV_FILE")" = 2 ]
  [ "$(grep -c '^A=' "$ENV_FILE")" -eq 1 ]
}

@test "env_set creates the file readable by the owner only" {
  skip_on_windows
  env_set A 1 "$ENV_FILE"
  [ "$(file_mode "$ENV_FILE")" = "rw-------" ]
}

@test "env_merge_defaults adds only missing keys and reports them" {
  printf 'A=custom\n' >"$ENV_FILE"
  printf '# a comment\nA=default\nB=2\n\nC=3\n' >"$BATS_TEST_TMPDIR/example"
  run env_merge_defaults "$BATS_TEST_TMPDIR/example" "$ENV_FILE"
  [ "$output" = "B C" ]
  [ "$(env_get A "$ENV_FILE")" = custom ]
  [ "$(env_get C "$ENV_FILE")" = 3 ]
}

@test "random_password gives 32 letters and digits, different each time" {
  local first second
  first="$(random_password)"
  second="$(random_password)"
  [ "${#first}" -eq 32 ]
  [[ "$first" =~ ^[A-Za-z0-9]+$ ]]
  [ "$first" != "$second" ]
}
