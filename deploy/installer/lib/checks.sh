# shellcheck shell=bash
# Machine checks made before anything changes: Docker, Compose, architecture, disk, memory,
# ports and openssl.

ASSAYR_MIN_FREE_GB="${ASSAYR_MIN_FREE_GB:-10}"
ASSAYR_MIN_COMPOSE="2.17.0"

docker_help() {
  case "$1" in
    macos) echo "Install and start Docker Desktop (https://docs.docker.com/desktop/setup/install/mac-install/) or Colima." ;;
    wsl) echo "Start Docker Desktop on Windows and turn on WSL integration for this distribution (Settings > Resources > WSL integration)." ;;
    *) echo "Install Docker Engine (https://docs.docker.com/engine/install/) and start it: systemctl start docker" ;;
  esac
}

check_docker() {
  local platform="$1" version
  command -v docker >/dev/null 2>&1 || die "Docker is not installed. $(docker_help "$platform")"
  docker info >/dev/null 2>&1 || die "Docker is installed but not running, or this user can't use it. $(docker_help "$platform")"
  version="$(docker compose version --short 2>/dev/null)" \
    || die "The Docker Compose plugin is missing. Install it: https://docs.docker.com/compose/install/"
  version="${version#v}"
  version="${version%%-*}"
  if version_gt "$ASSAYR_MIN_COMPOSE" "$version"; then
    die "Docker Compose $version is too old; Assayr needs $ASSAYR_MIN_COMPOSE or newer."
  fi
}

# check_arch BUNDLE_ARCH — the Docker host must run the bundle's architecture.
check_arch() {
  local raw machine
  raw="$(docker info --format '{{.Architecture}}' 2>/dev/null || true)"
  machine="$(normalize_arch "$raw")" \
    || die "This machine's architecture ($raw) isn't supported. Assayr runs on x86-64 (amd64) and arm64."
  [ "$machine" = "$1" ] \
    || die "This bundle is for $1 but this machine is $machine. Download assayr-<version>-linux-$machine-offline.tar.gz instead."
}

# free_kb PATH — free space in KB on the filesystem holding PATH or its nearest existing parent.
free_kb() {
  local path="$1"
  while [ ! -e "$path" ]; do path="$(dirname "$path")"; done
  df -Pk "$path" | awk 'NR==2 {print $4}'
}

check_disk() {
  local need="$ASSAYR_MIN_FREE_GB" kb
  [ "$need" -gt 0 ] || return 0
  kb="$(free_kb "$1")"
  [ "$kb" -ge $((need * 1024 * 1024)) ] \
    || die "At least $need GB of free disk space is needed for $1 (there is $((kb / 1024 / 1024)) GB)."
}

check_memory() {
  local bytes
  bytes="$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)"
  if [ "${bytes:-0}" -lt $((4 * 1024 * 1024 * 1024)) ]; then
    warn "Docker has less than 4 GB of memory. Malware scanning alone needs about 2 GB: give Docker more memory, or install with ASSAYR_MALWARE_SCAN=false."
  fi
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

check_port() {
  if port_in_use "$1"; then die "Port $1 is already in use. Free it or choose another port with $2."; fi
}

check_openssl() {
  command -v openssl >/dev/null 2>&1 \
    || die "openssl is needed to create a self-signed certificate. Install it, or give your own certificate with ASSAYR_TLS_CERT and ASSAYR_TLS_KEY."
}
