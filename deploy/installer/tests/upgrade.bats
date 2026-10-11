setup() {
  load helpers
  load_libs
  use_docker_stub
  OLD="$(make_bundle 1.2.3 "$BATS_TEST_TMPDIR/dist")"
  NEW="$(make_bundle 1.3.0 "$BATS_TEST_TMPDIR/dist")"
  DIR="$BATS_TEST_TMPDIR/install"
  install_fixture "$OLD" "$DIR" >/dev/null
  : >"$STUB_LOG"
  export STUB_IMAGES_PRESENT="$(stub_images 1.2.3) $(stub_images 1.3.0)"
}

@test "upgrade moves to the new version, keeps a backup and removes the old images" {
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Assayr is now 1.3.0 and running at https://localhost:18443."* ]]
  [ "$(cat "$DIR/VERSION")" = 1.3.0 ]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.3.0 ]
  [ ! -e "$DIR/.previous" ]
  [ -n "$(find "$DIR/backups" -name 'assayr-1.2.3-*.tar.gz')" ]
  grep -q "image rm assayr-api:1.2.3 assayr-web:1.2.3" "$STUB_LOG"
  grep -q "exec -T api assayr audit-verify" "$STUB_LOG"
}

@test "upgrade keeps existing settings and adds new ones with their defaults" {
  env_set ASSAYR_ORG_NAME "Custom Org" "$DIR/assayr.env"
  grep -v '^ASSAYR_WAIT_TIMEOUT=' "$DIR/assayr.env" >"$DIR/assayr.env.tmp"
  mv "$DIR/assayr.env.tmp" "$DIR/assayr.env"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"New settings added with their defaults: ASSAYR_WAIT_TIMEOUT"* ]]
  [ "$(env_get ASSAYR_ORG_NAME "$DIR/assayr.env")" = "Custom Org" ]
  [ "$(env_get ASSAYR_WAIT_TIMEOUT "$DIR/assayr.env")" = 600 ]
}

@test "the same or an older version is refused" {
  run "$OLD/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.2.3 is installed and this bundle is 1.2.3. upgrade only moves to a newer version."* ]]
  "$NEW/assayr" upgrade --dir "$DIR" >/dev/null
  run "$OLD/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.3.0 is installed and this bundle is 1.2.3."* ]]
}

@test "a new version that doesn't start is rolled back with the data from before the upgrade" {
  STUB_FAIL_ON="--wait-timeout" STUB_FAIL_TIMES=1 run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.3.0 did not start correctly. Rolling back to 1.2.3."* ]]
  [[ "$output" == *"The upgrade to 1.3.0 failed and was rolled back to 1.2.3. Your data is as it was before the upgrade."* ]]
  [ "$(cat "$DIR/VERSION")" = 1.2.3 ]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.2.3 ]
  [ ! -e "$DIR/.previous" ]
  grep -q pg_restore "$STUB_LOG"
  run grep -c "image rm assayr-api:1.2.3" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "when the rollback fails too, the message says where the data is" {
  STUB_FAIL_ON="--wait-timeout" run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the automatic rollback failed too. Your data is safe in $DIR/backups/assayr-1.2.3-"* ]]
}

@test "a failed backup stops the upgrade before anything changes" {
  STUB_FAIL_ON=pg_dump run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"The backup before the upgrade failed, so nothing was changed."* ]]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.2.3 ]
  run grep -c "load -i" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "an interrupted upgrade is put back before the next one" {
  mkdir "$DIR/.previous"
  cp "$DIR/assayr.env" "$DIR/.previous/assayr.env"
  env_set ASSAYR_ORG_NAME "Before the interruption" "$DIR/.previous/assayr.env"
  env_set ASSAYR_ORG_NAME "Half upgraded" "$DIR/assayr.env"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"An earlier upgrade did not finish."* ]]
  [ "$(env_get ASSAYR_ORG_NAME "$DIR/assayr.env")" = "Before the interruption" ]
  [ "$(cat "$DIR/VERSION")" = 1.3.0 ]
}

@test "upgrade without an installation says so" {
  run "$NEW/assayr" upgrade --dir "$BATS_TEST_TMPDIR/elsewhere"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No Assayr installation found in $BATS_TEST_TMPDIR/elsewhere."* ]]
}

@test "a half-written copy of the old program files is ignored" {
  mkdir -p "$DIR/.previous.tmp/lib"
  echo "partial" >"$DIR/.previous.tmp/lib/common.sh"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [ ! -e "$DIR/.previous.tmp" ]
  [ "$(cat "$DIR/VERSION")" = 1.3.0 ]
  grep -q "^ask() {" "$DIR/lib/common.sh"
}

@test "an upgrade interrupted after it finished is not undone" {
  "$NEW/assayr" upgrade --dir "$DIR" >/dev/null
  mkdir "$DIR/.previous.done"
  cp "$OLD/VERSION" "$DIR/.previous.done/VERSION"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.3.0 is installed and this bundle is 1.3.0."* ]]
  [ ! -e "$DIR/.previous.done" ]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.3.0 ]
}

@test "putting back an interrupted upgrade restores the version and warns about the database" {
  mkdir "$DIR/.previous"
  cp -R "$DIR/lib" "$DIR/assayr.env" "$DIR/VERSION" "$DIR/.previous/"
  echo 1.3.0 >"$DIR/VERSION"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"An earlier upgrade did not finish."* ]]
  [[ "$output" == *"may already have been changed by the new version"* ]]
  [ "$(cat "$DIR/VERSION")" = 1.3.0 ]
}

@test "an image whose tag exists but whose content differs is loaded again" {
  STUB_STALE_IMAGES="clamav/clamav-debian:1.4" run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  grep -qF "load -i $NEW/images/clamav_clamav-debian_1.4.tar" "$STUB_LOG"
  run grep -c "load -i $NEW/images/postgres_16-alpine.tar" "$STUB_LOG"
  [ "$output" = 0 ]
}
