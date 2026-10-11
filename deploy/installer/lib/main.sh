# shellcheck shell=bash
# Argument handling and dispatch for ./assayr.

main() {
  local command="${1:-help}" dir="" args=()
  if [ $# -gt 0 ]; then shift; fi
  trap run_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        need_value "$1" "${2:-}"
        dir="$2"
        shift 2
        ;;
      --yes)
        ASSAYR_ASSUME_YES=1
        shift
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done
  case "$command" in
    install | upgrade)
      [ -d "$SCRIPT_DIR/images" ] \
        || die "Run $command from an unpacked bundle (the folder that contains the images folder)."
      BUNDLE_DIR="$SCRIPT_DIR"
      if [ -n "$dir" ]; then args+=(--dir "$dir"); fi
      "cmd_$command" ${args[@]+"${args[@]}"}
      ;;
    status | start | stop | restart | logs | backup | restore | create-admin | uninstall)
      use_installation "$command" "$dir"
      "cmd_$(printf '%s' "$command" | tr - _)" ${args[@]+"${args[@]}"}
      ;;
    version) cmd_version ;;
    help | -h | --help) usage ;;
    *)
      usage >&2
      die "Unknown command: $command"
      ;;
  esac
}

# use_installation COMMAND DIR — find the installation (DIR, the folder this command lives in,
# or the platform default), then log to its install.log.
use_installation() {
  local command="$1" dir="$2" platform
  platform="$(detect_platform)"
  [ "$platform" != unsupported ] || die "This system isn't supported. Use Linux, macOS, or Windows inside WSL."
  require_privileges "$platform" "$command"
  if [ -z "$dir" ]; then
    if [ -f "$SCRIPT_DIR/assayr.env" ]; then dir="$SCRIPT_DIR"; else dir="$(default_install_dir "$platform")"; fi
  fi
  [ -f "$dir/assayr.env" ] || die "No Assayr installation found in $dir. Add --dir if it is installed elsewhere."
  ASSAYR_DIR="$(cd "$dir" && pwd)"
  log_to "$ASSAYR_DIR/install.log"
}
