# Shared setup for the installer tests. Load with: load helpers
bats_require_minimum_version 1.5.0 # for run ! and run -N
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

# use_docker_stub — run the installer against tests/stubs/docker, as root on Linux, with no
# free-disk requirement. Every docker call is recorded in $STUB_LOG.
use_docker_stub() {
  export PATH="$BATS_TEST_DIRNAME/stubs:$PATH"
  export STUB_LOG="$BATS_TEST_TMPDIR/docker.log"
  : >"$STUB_LOG"
  export ASSAYR_UNAME_S=Linux ASSAYR_PROC_VERSION="$BATS_TEST_TMPDIR/no-proc-version" ASSAYR_EUID=0
  export ASSAYR_MIN_FREE_GB=0
}

# stub_images VERSION — the four image references a bundle of VERSION contains.
stub_images() {
  echo "assayr-api:$1 assayr-web:$1 postgres:16-alpine clamav/clamav-debian:1.4"
}

# make_bundle VERSION OUTDIR — build a bundle folder with the docker stub; prints its path.
make_bundle() {
  STUB_IMAGES_PRESENT="$(stub_images "$1")" \
    "$REPO_ROOT/scripts/build-bundle.sh" "$1" amd64 "$2" --no-archive >/dev/null
  printf '%s\n' "$2/assayr-$1"
}

# install_fixture BUNDLE DIR [OPTIONS] — non-interactive install with the docker stub.
# STUB_IMAGES_PRESENT defaults to the bundle's images (set it to "" to make install load them).
install_fixture() {
  local bundle="$1" dir="$2"
  shift 2
  ASSAYR_HOSTNAME="${ASSAYR_HOSTNAME:-localhost}" ASSAYR_ORG_NAME="${ASSAYR_ORG_NAME-Test Org}" \
    ASSAYR_ADMIN_EMAIL="${ASSAYR_ADMIN_EMAIL-admin@example.com}" \
    ASSAYR_ADMIN_PASSWORD="${ASSAYR_ADMIN_PASSWORD:-test-password-123}" \
    STUB_IMAGES_PRESENT="${STUB_IMAGES_PRESENT-$(stub_images "$(cat "$bundle/VERSION")")}" \
    "$bundle/assayr" install --dir "$dir" --non-interactive --https-port 18443 --http-port 18080 "$@"
}
