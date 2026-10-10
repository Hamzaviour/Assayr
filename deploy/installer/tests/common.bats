setup() {
  load helpers
  load_libs
}

@test "text_problem refuses characters that would break the settings file" {
  local value
  for value in 'Acme $ Co' 'Acme "Co"' "Acme's" 'Acme \ Co' 'Acme # 1' 'Acme `Co`'; do
    [ -n "$(text_problem "Organisation name" "$value")" ] || { echo "accepted: $value"; return 1; }
  done
  [ -z "$(text_problem "Organisation name" "Acme Financial Services (PK) Ltd.")" ]
  [ "$(text_problem "Organisation name" "")" = "Organisation name can't be empty." ]
}

@test "hostname_problem accepts host names and IP addresses only" {
  local value
  for value in grc.corp.local localhost 10.0.0.5 assayr-01; do
    [ -z "$(hostname_problem "$value")" ] || { echo "refused: $value"; return 1; }
  done
  for value in "grc corp" -grc grc_corp ""; do
    [ -n "$(hostname_problem "$value")" ] || { echo "accepted: $value"; return 1; }
  done
}

@test "password_problem needs at least 12 characters" {
  [ "$(password_problem short)" = "The password must be at least 12 characters." ]
  [ -z "$(password_problem twelve-chars)" ]
}

@test "email_problem needs text on both sides of one @" {
  [ -z "$(email_problem admin@example.com)" ]
  [ -n "$(email_problem admin)" ]
  [ -n "$(email_problem "ad min@example.com")" ]
}

@test "port_problem accepts 1 to 65535" {
  [ -z "$(port_problem 443)" ]
  [ -n "$(port_problem 0)" ]
  [ -n "$(port_problem 70000)" ]
  [ -n "$(port_problem https)" ]
}

@test "ask keeps a value that is already set" {
  ASSAYR_INTERACTIVE=0
  FOO=preset
  ask FOO "Question" "default"
  [ "$FOO" = preset ]
}

@test "ask takes the default when running without questions" {
  ASSAYR_INTERACTIVE=0
  unset FOO
  ask FOO "Question" "default"
  [ "$FOO" = default ]
}

@test "ask without a default fails when running without questions" {
  ASSAYR_INTERACTIVE=0
  unset FOO
  run ask FOO "Question"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Set FOO when using --non-interactive."* ]]
}

@test "an optional question may stay empty" {
  ASSAYR_INTERACTIVE=0
  unset FOO
  ask FOO "Question" "" optional
  [ -z "$FOO" ]
}

@test "ask reads the answer, and asks again when a required answer is empty" {
  ASSAYR_INTERACTIVE=1
  unset FOO
  ask FOO "Question" <<'EOF'

typed answer
EOF
  [ "$FOO" = "typed answer" ]
}

@test "ask_password refuses a short password from the environment" {
  ASSAYR_INTERACTIVE=0
  PW=short
  run ask_password PW
  [ "$status" -eq 1 ]
  [[ "$output" == *"at least 12 characters"* ]]
}

@test "confirm_word cancels unless the word is typed" {
  ASSAYR_INTERACTIVE=1
  run confirm_word restore "This replaces your data." <<<"yes"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Cancelled; nothing was changed."* ]]
  run confirm_word restore "This replaces your data." <<<"restore"
  [ "$status" -eq 0 ]
}

@test "confirm_word with --yes needs no answer, and without questions it needs --yes" {
  ASSAYR_ASSUME_YES=1
  run confirm_word restore "This replaces your data."
  [ "$status" -eq 0 ]
  ASSAYR_ASSUME_YES=0
  ASSAYR_INTERACTIVE=0
  run confirm_word restore "This replaces your data."
  [ "$status" -eq 1 ]
  [[ "$output" == *"Add --yes"* ]]
}

@test "run_logged sends command output to the log only" {
  log_to "$BATS_TEST_TMPDIR/install.log"
  run run_logged echo hello-from-the-command
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  grep -q "RUN echo hello-from-the-command" "$BATS_TEST_TMPDIR/install.log"
  grep -q "^hello-from-the-command$" "$BATS_TEST_TMPDIR/install.log"
}

@test "die prints the retry hint and where the details are" {
  log_to "$BATS_TEST_TMPDIR/install.log"
  ASSAYR_RETRY_HINT="To start again: uninstall, then install."
  run die "Something broke."
  [ "$status" -eq 1 ]
  [[ "$output" == *"Error: Something broke."* ]]
  [[ "$output" == *"To start again: uninstall, then install."* ]]
  [[ "$output" == *"Details: $BATS_TEST_TMPDIR/install.log"* ]]
}

@test "need_value refuses a missing option value" {
  run need_value --dir ""
  [ "$status" -eq 1 ]
  [[ "$output" == *"--dir needs a value."* ]]
  run need_value --dir --http
  [ "$status" -eq 1 ]
}
