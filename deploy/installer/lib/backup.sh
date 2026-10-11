# shellcheck shell=bash
# Backups: one archive with the database dump, the evidence files, the settings and a manifest.

BACKUP_FILE=""
RESTORE_FOLDER=""
RESTORE_PROBLEM=""

# do_backup DEST_DIR — sets BACKUP_FILE. On failure returns 1 and leaves nothing behind.
do_backup() {
  local dest="$1" version stamp name work
  BACKUP_FILE=""
  version="$(bundle_value "$ASSAYR_DIR" VERSION)"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  name="assayr-$version-$stamp"
  if [ ! -d "$dest" ]; then
    mkdir -p "$dest" || return 1
    chmod 700 "$dest"
  fi
  dest="$(cd "$dest" && pwd)"
  if [ -e "$dest/$name.tar.gz" ]; then name="$name-2"; fi
  work="$(mktemp -d "$dest/.backup.XXXXXX")" || return 1
  # An interrupted backup must not leave the dump behind; the archive only appears, by rename,
  # once it is complete.
  remove_on_exit "$work"
  if ! mkdir "$work/$name" || ! backup_parts "$work/$name" \
    || ! printf 'version=%s\ncreated=%s\n' "$version" "$stamp" >"$work/$name/manifest.txt" \
    || ! write_sums "$work/$name" \
    || ! (umask 077 && tar -C "$work" -czf "$work/$name.tar.gz" "$name") \
    || ! chmod 600 "$work/$name.tar.gz" \
    || ! mv "$work/$name.tar.gz" "$dest/$name.tar.gz"; then
    rm -rf "$work"
    return 1
  fi
  rm -rf "$work"
  BACKUP_FILE="$dest/$name.tar.gz"
}

backup_parts() {
  local part="$1"
  run_logged assayr_compose up -d --wait db || return 1
  _log_line "RUN pg_dump"
  assayr_compose exec -T db pg_dump -U assayr -d assayr -Fc >"$part/db.dump" 2>>"${ASSAYR_LOG:-/dev/null}" || return 1
  run_logged assayr_compose run --rm --no-deps -T --user root --entrypoint tar -v "$part:/backup" api \
    -C /data/blobs -cf /backup/blobs.tar . || return 1
  cp "$ASSAYR_DIR/assayr.env" "$part/assayr.env" || return 1
  cp -R "$ASSAYR_DIR/certs" "$part/certs" || return 1
  cp -R "$ASSAYR_DIR/license" "$part/license"
}

# The parts a restore can't do without; each must exist and be in the checksum list.
BACKUP_REQUIRED="manifest.txt db.dump blobs.tar"

# read_backup ARCHIVE WORKDIR — unpack and check a backup. Sets RESTORE_FOLDER, or sets
# RESTORE_PROBLEM and returns 1.
read_backup() {
  local archive="$1" work="$2" folder problem part
  RESTORE_FOLDER=""
  RESTORE_PROBLEM=""
  if ! tar -C "$work" -xzf "$archive" 2>/dev/null; then
    RESTORE_PROBLEM="it can't be unpacked."
    return 1
  fi
  folder="$(find "$work" -mindepth 1 -maxdepth 1 -type d -name 'assayr-*' | head -n 1)"
  if [ -z "$folder" ] || [ ! -f "$folder/manifest.txt" ]; then
    RESTORE_PROBLEM="it has no manifest."
    return 1
  fi
  if ! problem="$(verify_bundle "$folder")"; then
    RESTORE_PROBLEM="$problem"
    return 1
  fi
  for part in $BACKUP_REQUIRED; do
    if [ ! -f "$folder/$part" ]; then
      RESTORE_PROBLEM="$part is missing."
      return 1
    fi
    if ! awk -v want="./$part" '$2 == want { found = 1 } END { exit !found }' "$folder/SHA256SUMS" 2>/dev/null; then
      RESTORE_PROBLEM="$part is not in its checksum list."
      return 1
    fi
  done
  RESTORE_FOLDER="$folder"
}

# restore_data FOLDER — replace the database and the evidence files, then start Assayr.
restore_data() {
  local folder="$1"
  run_logged assayr_compose stop api worker web || return 1
  run_logged assayr_compose up -d --wait db || return 1
  run_logged assayr_compose exec -T db dropdb -U assayr --if-exists assayr || return 1
  run_logged assayr_compose exec -T db createdb -U assayr -O assayr assayr || return 1
  _log_line "RUN pg_restore"
  assayr_compose exec -T db pg_restore -U assayr -d assayr --no-owner --exit-on-error \
    <"$folder/db.dump" >>"${ASSAYR_LOG:-/dev/null}" 2>&1 || return 1
  run_logged assayr_compose run --rm --no-deps -T --user root --entrypoint sh -v "$folder:/backup:ro" api \
    -c 'find /data/blobs -mindepth 1 -delete && tar -C /data/blobs -xf /backup/blobs.tar && chown -R assayr:assayr /data/blobs' \
    || return 1
  start_stack
}
