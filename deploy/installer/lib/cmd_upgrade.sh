# shellcheck shell=bash
# ./assayr upgrade — move an installation to this bundle's version, rolling back on failure.

cmd_upgrade() {
  local dir="" platform new old backup added problem
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        need_value "$1" "${2:-}"
        dir="$2"
        shift 2
        ;;
      --non-interactive)
        ASSAYR_INTERACTIVE=0
        shift
        ;;
      *) die "Unknown option for upgrade: $1. Run ./assayr help." ;;
    esac
  done
  platform="$(detect_platform)"
  [ "$platform" != unsupported ] || die "This system isn't supported. Use Linux, macOS, or Windows inside WSL."
  require_privileges "$platform" upgrade
  dir="${dir:-$(default_install_dir "$platform")}"
  [ -f "$dir/assayr.env" ] \
    || die "No Assayr installation found in $dir. Use ./assayr install, or add --dir if it is installed elsewhere."
  ASSAYR_DIR="$(cd "$dir" && pwd)"
  log_to "$ASSAYR_DIR/install.log"
  finish_interrupted_upgrade

  new="$(bundle_value "$BUNDLE_DIR" VERSION)"
  old="$(bundle_value "$ASSAYR_DIR" VERSION)"
  version_gt "$new" "$old" \
    || die "Assayr $old is installed and this bundle is $new. upgrade only moves to a newer version."

  info "Checking this machine"
  check_docker "$platform"
  check_arch "$(bundle_value "$BUNDLE_DIR" ARCH)"
  check_disk "$ASSAYR_DIR"
  info "Checking the bundle"
  problem="$(verify_bundle "$BUNDLE_DIR")" \
    || die "This bundle is damaged or was modified: $problem Download it again and compare its checksum with the one on the release page."

  info "Backing up Assayr $old before the upgrade"
  do_backup "$ASSAYR_DIR/backups" || die "The backup before the upgrade failed, so nothing was changed."
  backup="$BACKUP_FILE"
  info "Loading the $new images (this takes a few minutes)"
  load_images "$BUNDLE_DIR" || die "Loading the images failed; nothing else was changed."

  info "Installing the $new program files"
  mkdir "$ASSAYR_DIR/.previous"
  copy_program_files "$ASSAYR_DIR" "$ASSAYR_DIR/.previous"
  cp "$ASSAYR_DIR/assayr.env" "$ASSAYR_DIR/.previous/assayr.env"
  copy_program_files "$BUNDLE_DIR" "$ASSAYR_DIR"
  env_set ASSAYR_VERSION "$new" "$ASSAYR_DIR/assayr.env"
  added="$(env_merge_defaults "$ASSAYR_DIR/assayr.env.example" "$ASSAYR_DIR/assayr.env")"
  if [ -n "$added" ]; then info "New settings added with their defaults: $added"; fi

  info "Starting Assayr $new (the database is migrated on start)"
  if start_stack && api_ready && audit_ok; then
    cp "$BUNDLE_DIR/VERSION" "$ASSAYR_DIR/VERSION"
    rm -rf "$ASSAYR_DIR/.previous"
    run_logged docker image rm "assayr-api:$old" "assayr-web:$old" || true
    info "Assayr is now $new and running at $(install_url). The backup taken before the upgrade is $backup"
    return 0
  fi
  warn "Assayr $new did not start correctly. Rolling back to $old."
  if rollback_upgrade "$backup"; then
    die "The upgrade to $new failed and was rolled back to $old. Your data is as it was before the upgrade."
  fi
  die "The upgrade to $new failed and the automatic rollback failed too. Your data is safe in $backup. Restore it with the $old bundle's command: ./assayr restore $backup"
}

# finish_interrupted_upgrade — an upgrade stopped half-way leaves .previous/: put it back.
finish_interrupted_upgrade() {
  [ -d "$ASSAYR_DIR/.previous" ] || return 0
  warn "An earlier upgrade did not finish. Putting back the program files and settings of Assayr $(bundle_value "$ASSAYR_DIR" VERSION) first."
  copy_program_files "$ASSAYR_DIR/.previous" "$ASSAYR_DIR"
  cp "$ASSAYR_DIR/.previous/assayr.env" "$ASSAYR_DIR/assayr.env"
  rm -rf "$ASSAYR_DIR/.previous"
}

# rollback_upgrade BACKUP_FILE — previous program files and settings, then the data from BACKUP_FILE.
rollback_upgrade() {
  local backup="$1" work ok=1
  run_logged assayr_compose down --remove-orphans || true
  copy_program_files "$ASSAYR_DIR/.previous" "$ASSAYR_DIR"
  cp "$ASSAYR_DIR/.previous/assayr.env" "$ASSAYR_DIR/assayr.env"
  rm -rf "$ASSAYR_DIR/.previous"
  work="$(mktemp -d "$ASSAYR_DIR/backups/.rollback.XXXXXX")"
  if read_backup "$backup" "$work" && restore_data "$RESTORE_FOLDER" && api_ready; then ok=0; fi
  rm -rf "$work"
  return "$ok"
}
