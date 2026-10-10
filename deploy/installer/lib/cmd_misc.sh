# shellcheck shell=bash
# Day-to-day commands for an installation.

usage() {
  cat <<'EOF'
Assayr installer and administration

From an unpacked bundle:
  install        Install Assayr (asks a few questions; see README-INSTALL.md)
                   --dir DIR  --license FILE  --http  --https-port N  --http-port N  --non-interactive
  upgrade        Upgrade an installation to this bundle's version (backs up first, rolls back on failure)
                   --dir DIR

From the installation folder (or with --dir DIR):
  status         Version, address, services and free disk
  backup         Back up the database, evidence files and settings   --to DIR
  restore        Replace all data with a backup                      FILE [--yes]
  start          Start Assayr
  stop           Stop Assayr
  restart        Restart Assayr (after changing assayr.env or the certificate)
  logs           Follow the logs                                     [SERVICE]
  create-admin   Create another administrator account
  uninstall      Stop and remove the containers; --delete-data also deletes all data
  version        Show the version
  help           Show this help
EOF
}

cmd_version() {
  echo "Assayr $(bundle_value "$SCRIPT_DIR" VERSION || echo unknown) ($(bundle_value "$SCRIPT_DIR" ARCH || echo unknown))"
}

cmd_status() {
  local backups
  echo "Assayr $(bundle_value "$ASSAYR_DIR" VERSION) ($(bundle_value "$ASSAYR_DIR" ARCH)) in $ASSAYR_DIR"
  echo "Address: $(install_url)"
  echo
  assayr_compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}' || true
  echo
  if api_ready; then
    echo "Application: ready"
  else
    echo "Application: not ready (see: $(sudo_prefix)$ASSAYR_DIR/assayr logs api)"
  fi
  backups="$(find "$ASSAYR_DIR/backups" -maxdepth 1 -name 'assayr-*.tar.gz' | wc -l | tr -d ' ')"
  echo "Backups: $backups in $ASSAYR_DIR/backups"
  df -Ph "$ASSAYR_DIR" | awk 'NR==2 {print "Free disk: " $4}'
}

cmd_start() {
  info "Starting Assayr"
  start_stack || die "Assayr did not start. See: $(sudo_prefix)$ASSAYR_DIR/assayr logs api"
  info "Assayr is running at $(install_url)"
}

cmd_stop() {
  info "Stopping Assayr"
  run_logged assayr_compose stop || die "Stopping Assayr failed."
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_logs() {
  assayr_compose logs --tail 200 --follow "$@"
}

cmd_create_admin() {
  local problem
  while [ $# -gt 0 ]; do
    case "$1" in
      --non-interactive)
        ASSAYR_INTERACTIVE=0
        shift
        ;;
      *) die "Unknown option for create-admin: $1" ;;
    esac
  done
  ask ASSAYR_ADMIN_EMAIL "Administrator email"
  problem="$(email_problem "$ASSAYR_ADMIN_EMAIL")"
  [ -z "$problem" ] || die "$problem"
  ask_password ASSAYR_ADMIN_PASSWORD
  info "Creating the administrator $ASSAYR_ADMIN_EMAIL"
  create_admin_account "$ASSAYR_ADMIN_EMAIL" "$ASSAYR_ADMIN_PASSWORD" \
    || die "Creating the administrator failed. A user with that email may already exist."
  info "Done. $ASSAYR_ADMIN_EMAIL can sign in at $(install_url)"
}

cmd_uninstall() {
  local delete=0 version
  while [ $# -gt 0 ]; do
    case "$1" in
      --delete-data)
        delete=1
        shift
        ;;
      *) die "Unknown option for uninstall: $1" ;;
    esac
  done
  if [ "$delete" = 0 ]; then
    info "Stopping Assayr and removing its containers"
    run_logged assayr_compose down --remove-orphans || die "Removing the containers failed."
    info "Done. The data, settings and backups are kept in $ASSAYR_DIR and in Docker volumes. To bring Assayr back: $(sudo_prefix)$ASSAYR_DIR/assayr start"
    return 0
  fi
  confirm_word delete "This permanently deletes Assayr and all its data: the database, the evidence files, the settings, the certificates and every backup in $ASSAYR_DIR."
  version="$(bundle_value "$ASSAYR_DIR" VERSION 2>/dev/null || true)"
  run_logged assayr_compose down -v --remove-orphans || die "Removing the containers and data volumes failed."
  if [ -n "$version" ]; then
    run_logged docker image rm "assayr-api:$version" "assayr-web:$version" || true
  fi
  ASSAYR_LOG=""
  rm -rf "${ASSAYR_DIR:?}"
  echo "Assayr has been removed."
}

cmd_backup() {
  local dest="$ASSAYR_DIR/backups"
  while [ $# -gt 0 ]; do
    case "$1" in
      --to)
        need_value "$1" "${2:-}"
        dest="$2"
        shift 2
        ;;
      *) die "Unknown option for backup: $1" ;;
    esac
  done
  info "Backing up Assayr"
  do_backup "$dest" || die "The backup failed. Nothing was written."
  info "Backup written to $BACKUP_FILE"
  echo "It contains the database password and the HTTPS private key: keep it where only administrators can read it."
}

cmd_restore() {
  local file="" work backup_version installed created safety
  while [ $# -gt 0 ]; do
    case "$1" in
      -*) die "Unknown option for restore: $1" ;;
      *)
        file="$1"
        shift
        ;;
    esac
  done
  [ -n "$file" ] || die "Give the backup file: ./assayr restore FILE"
  [ -f "$file" ] || die "Backup file not found: $file"
  work="$(mktemp -d "$ASSAYR_DIR/backups/.restore.XXXXXX")"
  # shellcheck disable=SC2064 # expand $work now
  trap "rm -rf '$work'" EXIT
  read_backup "$file" "$work" || die "This backup can't be used: $RESTORE_PROBLEM"
  backup_version="$(env_get version "$RESTORE_FOLDER/manifest.txt")"
  created="$(env_get created "$RESTORE_FOLDER/manifest.txt")"
  installed="$(bundle_value "$ASSAYR_DIR" VERSION)"
  if version_gt "$backup_version" "$installed"; then
    die "This backup was made by Assayr $backup_version, which is newer than the installed $installed. Upgrade to $backup_version or later first."
  fi
  confirm_word restore "Restoring replaces all current Assayr data with the backup taken at $created (Assayr $backup_version)."
  info "Taking a safety backup of the current data"
  do_backup "$ASSAYR_DIR/backups" || die "The safety backup failed, so nothing was restored."
  safety="$BACKUP_FILE"
  info "Restoring the database and the evidence files"
  restore_data "$RESTORE_FOLDER" \
    || die "The restore failed. The data from just before it is in $safety. To put it back: $(sudo_prefix)$ASSAYR_DIR/assayr restore $safety"
  if audit_ok; then
    info "Restore complete. The audit trail is intact."
  else
    warn "Restore complete, but the audit trail check failed. See $ASSAYR_LOG"
  fi
}
