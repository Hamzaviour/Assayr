setup() {
  load helpers
  load_libs
  use_docker_stub
  BUNDLE="$(make_bundle 1.2.3 "$BATS_TEST_TMPDIR/dist")"
  DIR="$BATS_TEST_TMPDIR/install"
  install_fixture "$BUNDLE" "$DIR" >/dev/null
  : >"$STUB_LOG"
}

only_backup() {
  find "$DIR/backups" -maxdepth 1 -name 'assayr-*.tar.gz' | head -n 1
}

# repack_backup FILE EDIT — unpack FILE, run EDIT in its folder, write it back as FILE.
repack_backup() {
  local file="$1" edit="$2" work="$BATS_TEST_TMPDIR/repack" folder
  rm -rf "$work"
  mkdir -p "$work"
  tar -C "$work" -xzf "$file"
  folder="$(find "$work" -mindepth 1 -maxdepth 1 -type d)"
  (cd "$folder" && eval "$edit")
  tar -C "$work" -czf "$file" "$(basename "$folder")"
}

@test "backup writes one archive with the database, evidence files, settings and a manifest" {
  run "$DIR/assayr" backup
  [ "$status" -eq 0 ]
  [[ "$output" == *"Backup written to $DIR/backups/assayr-1.2.3-"* ]]
  [[ "$output" == *"where only administrators can read it"* ]]
  local file
  file="$(only_backup)"
  run tar -tzf "$file"
  local part
  for part in db.dump blobs.tar assayr.env certs/tls.crt certs/tls.key manifest.txt SHA256SUMS; do
    [[ "$output" == *"/$part"* ]] || { echo "missing $part"; return 1; }
  done
  grep -q "exec -T db pg_dump -U assayr -d assayr -Fc" "$STUB_LOG"
  [ -z "$(find "$DIR/backups" -name '.backup.*')" ]
}

@test "backup archives are readable by the owner only" {
  skip_on_windows
  "$DIR/assayr" backup >/dev/null
  [ "$(file_mode "$(only_backup)")" = "rw-------" ]
}

@test "backup --to writes the archive to another folder" {
  run "$DIR/assayr" backup --to "$BATS_TEST_TMPDIR/offsite copies"
  [ "$status" -eq 0 ]
  [ -n "$(find "$BATS_TEST_TMPDIR/offsite copies" -name 'assayr-1.2.3-*.tar.gz')" ]
}

@test "a failed backup leaves nothing behind" {
  STUB_FAIL_ON=pg_dump run "$DIR/assayr" backup
  [ "$status" -eq 1 ]
  [[ "$output" == *"The backup failed. Nothing was written."* ]]
  [ -z "$(find "$DIR/backups" -mindepth 1)" ]
}

@test "restore takes a safety backup, then puts back the database and the evidence files" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  : >"$STUB_LOG"
  sleep 1 # the safety backup gets its own timestamp
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"Restore complete. The audit trail is intact."* ]]
  [ "$(find "$DIR/backups" -maxdepth 1 -name 'assayr-*.tar.gz' | wc -l | tr -d ' ')" -eq 2 ]
  # line TEXT — line number in the docker log of the last call containing TEXT
  line() { grep -n -- "$1" "$STUB_LOG" | tail -n 1 | cut -d: -f1; }
  [ "$(line pg_dump)" -lt "$(line dropdb)" ]
  [ "$(line dropdb)" -lt "$(line createdb)" ]
  [ "$(line createdb)" -lt "$(line pg_restore)" ]
  [ "$(line pg_restore)" -lt "$(line 'tar -C /data/blobs -xf')" ]
  [ "$(line 'tar -C /data/blobs -xf')" -lt "$(line --wait-timeout)" ]
  [ -z "$(find "$DIR/backups" -name '.restore.*')" ]
}

@test "restore asks for confirmation" {
  "$DIR/assayr" backup >/dev/null
  run "$DIR/assayr" restore "$(only_backup)" </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"Cancelled; nothing was changed."* ]]
  run grep -c dropdb "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "restore refuses a damaged backup" {
  echo "not a backup" >"$BATS_TEST_TMPDIR/broken.tar.gz"
  run "$DIR/assayr" restore "$BATS_TEST_TMPDIR/broken.tar.gz" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"This backup can't be used: it can't be unpacked."* ]]

  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  repack_backup "$file" 'echo tampered >>db.dump'
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"./db.dump does not match its checksum."* ]]
  run grep -c dropdb "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "restore refuses a backup from a newer version" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  repack_backup "$file" "printf 'version=9.9.9\ncreated=20991231T000000Z\n' >manifest.txt && . '$INSTALLER/lib/bundle.sh' && write_sums ."
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"This backup was made by Assayr 9.9.9, which is newer than the installed 1.2.3."* ]]
}

@test "when the restore fails, it points to the safety backup" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  sleep 1
  STUB_FAIL_ON=pg_restore run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"The restore failed. The data from just before it is in $DIR/backups/assayr-1.2.3-"* ]]
}

@test "restore refuses a backup whose checksum list leaves out a part" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  repack_backup "$file" "rm db.dump && grep -v ' ./db.dump$' SHA256SUMS >S && mv S SHA256SUMS"
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"This backup can't be used: db.dump is missing."* ]]
  run grep -c dropdb "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "a backup stopped part-way leaves no archive and no temporary folder" {
  STUB_BLOCK_ON=pg_dump "$DIR/assayr" backup >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 50); do grep -q pg_dump "$STUB_LOG" && break; sleep 0.2; done
  kill -TERM "$pid"
  wait "$pid" || true
  [ -z "$(find "$DIR/backups" -mindepth 1)" ]
}
