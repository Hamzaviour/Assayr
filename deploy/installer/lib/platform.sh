# shellcheck shell=bash
# Which system we are on, where Assayr lives there, and who may install it.

detect_platform() {
  local kernel="${ASSAYR_UNAME_S:-$(uname -s)}" version_file="${ASSAYR_PROC_VERSION:-/proc/version}"
  case "$kernel" in
    Darwin) echo macos ;;
    Linux)
      if [ -r "$version_file" ] && grep -qi microsoft "$version_file"; then echo wsl; else echo linux; fi
      ;;
    *) echo unsupported ;;
  esac
}

# normalize_arch NAME — Docker's or uname's architecture name as amd64 or arm64.
normalize_arch() {
  case "$1" in
    x86_64 | amd64) echo amd64 ;;
    aarch64 | arm64) echo arm64 ;;
    *)
      echo "$1"
      return 1
      ;;
  esac
}

default_install_dir() {
  case "$1" in
    linux) echo /opt/assayr ;;
    *) echo "$HOME/assayr" ;;
  esac
}

default_hostname() {
  case "$1" in
    linux) hostname -f 2>/dev/null || hostname ;;
    *) echo localhost ;;
  esac
}

evaluation_notice() {
  case "$1" in
    macos | wsl) warn "This setup is for evaluation. Run Assayr in production on a Linux server." ;;
  esac
}

require_privileges() {
  if [ "$1" = linux ] && [ "${ASSAYR_EUID:-$(id -u)}" -ne 0 ]; then
    die "Run this as root, for example: sudo ./assayr $2"
  fi
}

# sudo_prefix — "sudo " where commands need root, for the hints we print.
sudo_prefix() {
  if [ "$(detect_platform)" = linux ]; then echo "sudo "; fi
}
