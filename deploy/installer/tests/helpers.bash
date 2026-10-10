# Shared setup for the installer tests. Load with: load helpers
REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
INSTALLER="$REPO_ROOT/deploy/installer"

# Source every installer library that exists so far.
load_libs() {
  local part
  for part in common platform envfile bundle checks certs compose backup cmd_install cmd_upgrade cmd_misc main; do
    if [ -f "$INSTALLER/lib/$part.sh" ]; then
      # shellcheck source=/dev/null
      . "$INSTALLER/lib/$part.sh"
    fi
  done
}

on_windows() {
  case "$(uname -s)" in MINGW* | MSYS* | CYGWIN*) return 0 ;; esac
  return 1
}

skip_on_windows() {
  if on_windows; then skip "file modes aren't meaningful on Windows"; fi
}

# file_mode PATH — permission bits as ls shows them, e.g. rw-------
file_mode() {
  ls -ld "$1" | cut -c2-10
}
