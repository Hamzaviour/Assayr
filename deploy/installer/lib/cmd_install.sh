# shellcheck shell=bash
# ./assayr install — the first installation, from an unpacked bundle.

cmd_install() {
  local dir="" license="" web_mode=https https_port=443 http_port="" platform problem
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        need_value "$1" "${2:-}"
        dir="$2"
        shift 2
        ;;
      --license)
        need_value "$1" "${2:-}"
        license="$2"
        shift 2
        ;;
      --http)
        web_mode=http
        shift
        ;;
      --https-port)
        need_value "$1" "${2:-}"
        https_port="$2"
        shift 2
        ;;
      --http-port)
        need_value "$1" "${2:-}"
        http_port="$2"
        shift 2
        ;;
      --non-interactive)
        ASSAYR_INTERACTIVE=0
        shift
        ;;
      *) die "Unknown option for install: $1. Run ./assayr help." ;;
    esac
  done
  if [ -z "$http_port" ]; then
    if [ "$web_mode" = https ]; then http_port=80; else http_port=8080; fi
  fi
  problem="$(port_problem "$https_port")$(port_problem "$http_port")"
  [ -z "$problem" ] || die "$problem"

  platform="$(detect_platform)"
  [ "$platform" != unsupported ] || die "This system isn't supported. Install on Linux, on macOS, or on Windows inside WSL."
  require_privileges "$platform" install
  evaluation_notice "$platform"
  dir="${dir:-$(default_install_dir "$platform")}"
  [ ! -f "$dir/assayr.env" ] \
    || die "Assayr is already installed in $dir. To move to a newer version, run ./assayr upgrade from the new bundle."
  # uninstall --delete-data removes what install created and then the folder only if it is empty,
  # but a folder of other files must never become an install folder.
  if [ -d "$dir" ] && [ -n "$(ls -A "$dir")" ]; then
    die "$dir isn't empty. Choose a new or empty folder with --dir."
  fi

  info "Checking this machine"
  check_docker "$platform"
  check_no_other_installation
  check_arch "$(bundle_value "$BUNDLE_DIR" ARCH)"
  check_disk "$dir"
  check_memory
  check_port "$http_port" --http-port
  if [ "$web_mode" = https ]; then check_port "$https_port" --https-port; fi
  if [ -n "$license" ] && [ ! -f "$license" ]; then die "Licence file not found: $license"; fi

  info "Checking the bundle"
  problem="$(verify_bundle "$BUNDLE_DIR")" \
    || die "This bundle is damaged or was modified: $problem Download it again and compare its checksum with the one on the release page."

  collect_install_answers "$platform" "$web_mode"

  info "Writing the installation to $dir"
  mkdir -p "$dir"
  ASSAYR_DIR="$(cd "$dir" && pwd)"
  log_to "$ASSAYR_DIR/install.log"
  ASSAYR_RETRY_HINT="To start again: $(sudo_prefix)$ASSAYR_DIR/assayr uninstall --delete-data, then run install again."
  copy_program_files "$BUNDLE_DIR" "$ASSAYR_DIR"
  cp "$BUNDLE_DIR/VERSION" "$ASSAYR_DIR/VERSION"
  mkdir -p "$ASSAYR_DIR/certs" "$ASSAYR_DIR/license" "$ASSAYR_DIR/backups"
  chmod 700 "$ASSAYR_DIR/license" "$ASSAYR_DIR/backups"
  write_install_env "$web_mode" "$https_port" "$http_port"
  install_certificate "$web_mode"
  if [ -n "$license" ]; then
    cp "$license" "$ASSAYR_DIR/license/assayr.lic"
    chmod 600 "$ASSAYR_DIR/license/assayr.lic"
  fi

  info "Loading the container images (this takes a few minutes)"
  load_images "$BUNDLE_DIR" || die "Loading the images failed."
  info "Starting Assayr (the first start prepares the database)"
  start_stack || die "Assayr did not start. See $(sudo_prefix)$ASSAYR_DIR/assayr logs api"
  info "Creating the administrator account"
  create_admin_account "$ASSAYR_ADMIN_EMAIL" "$ASSAYR_ADMIN_PASSWORD" \
    || die "Assayr is running, but creating the administrator failed. Try again with: $(sudo_prefix)$ASSAYR_DIR/assayr create-admin"
  ASSAYR_RETRY_HINT=""
  print_install_summary "$web_mode"
}

# check_no_other_installation — every installation uses the compose project "assayr", so a second
# one would take over the first one's containers and data volumes.
check_no_other_installation() {
  local volume
  for volume in assayr_dbdata assayr_blobs; do
    if docker volume inspect "$volume" >/dev/null 2>&1; then
      die "Docker on this machine already has an Assayr installation (its data volume $volume exists). Only one installation per machine is supported. To move it to this version, run ./assayr upgrade --dir <its folder>. To remove it and all its data, run assayr uninstall --delete-data from its folder."
    fi
  done
  if [ -n "$(docker ps -a -q --filter label=com.docker.compose.project=assayr 2>/dev/null)" ]; then
    die "Docker on this machine already has an Assayr installation (its containers exist). Only one installation per machine is supported. To move it to this version, run ./assayr upgrade --dir <its folder>. To remove it, run assayr uninstall from its folder."
  fi
}

collect_install_answers() {
  local platform="$1" web_mode="$2" problem
  ask ASSAYR_HOSTNAME "Hostname users will type in the browser" "$(default_hostname "$platform")"
  problem="$(hostname_problem "$ASSAYR_HOSTNAME")"
  [ -z "$problem" ] || die "$problem"
  ask ASSAYR_ORG_NAME "Organisation name" "My Organization"
  problem="$(text_problem "Organisation name" "$ASSAYR_ORG_NAME")"
  [ -z "$problem" ] || die "$problem"
  if [ "$web_mode" = https ]; then
    ask ASSAYR_TLS_CERT "HTTPS certificate file (press Enter to create a self-signed one)" "" optional
    if [ -n "$ASSAYR_TLS_CERT" ]; then
      ask ASSAYR_TLS_KEY "Private key file for that certificate"
      [ -f "$ASSAYR_TLS_CERT" ] || die "Certificate file not found: $ASSAYR_TLS_CERT"
      [ -f "$ASSAYR_TLS_KEY" ] || die "Key file not found: $ASSAYR_TLS_KEY"
    else
      check_openssl
    fi
  else
    ask ASSAYR_BEHIND_TLS_PROXY "Is there an HTTPS proxy in front of Assayr? (yes/no)" "no"
  fi
  ask ASSAYR_ADMIN_EMAIL "Administrator email"
  problem="$(email_problem "$ASSAYR_ADMIN_EMAIL")"
  [ -z "$problem" ] || die "$problem"
  ask_password ASSAYR_ADMIN_PASSWORD
}

write_install_env() {
  local web_mode="$1" https_port="$2" http_port="$3" env="$ASSAYR_DIR/assayr.env"
  local secure=true scan="${ASSAYR_MALWARE_SCAN:-true}"
  if [ "$web_mode" = http ]; then
    case "${ASSAYR_BEHIND_TLS_PROXY:-no}" in
      y | Y | yes | Yes | YES) secure=true ;;
      *)
        secure=false
        warn "Assayr will be served over plain HTTP. Use this only for evaluation."
        ;;
    esac
  fi
  (umask 077 && cp "$ASSAYR_DIR/assayr.env.example" "$env")
  env_set ASSAYR_VERSION "$(bundle_value "$BUNDLE_DIR" VERSION)" "$env"
  env_set POSTGRES_PASSWORD "$(random_password)" "$env"
  env_set ASSAYR_HOSTNAME "$ASSAYR_HOSTNAME" "$env"
  env_set ASSAYR_ORG_NAME "$ASSAYR_ORG_NAME" "$env"
  env_set ASSAYR_WEB_MODE "$web_mode" "$env"
  env_set ASSAYR_HTTPS_PORT "$https_port" "$env"
  env_set ASSAYR_HTTP_PORT "$http_port" "$env"
  env_set ASSAYR_SECURE_COOKIES "$secure" "$env"
  env_set ASSAYR_MALWARE_SCAN "$scan" "$env"
  if [ "$scan" = true ]; then
    env_set ASSAYR_CLAMAV_HOST clamav "$env"
  else
    env_set ASSAYR_CLAMAV_HOST "" "$env"
  fi
}

install_certificate() {
  local cert="$ASSAYR_DIR/certs/tls.crt" key="$ASSAYR_DIR/certs/tls.key"
  [ "$1" = https ] || return 0
  if [ -n "${ASSAYR_TLS_CERT:-}" ]; then
    cp "$ASSAYR_TLS_CERT" "$cert"
    (umask 077 && cp "$ASSAYR_TLS_KEY" "$key")
  else
    info "Creating a self-signed certificate for $ASSAYR_HOSTNAME"
    make_self_signed "$ASSAYR_HOSTNAME" "$cert" "$key" || die "Creating the self-signed certificate failed."
  fi
  chmod 644 "$cert"
  chmod 600 "$key"
}

print_install_summary() {
  local sudo
  sudo="$(sudo_prefix)"
  echo
  echo "Assayr $(bundle_value "$ASSAYR_DIR" VERSION) is running."
  echo "  Address:        $(install_url)"
  echo "  Administrator:  $ASSAYR_ADMIN_EMAIL"
  if [ "$1" = https ] && [ -z "${ASSAYR_TLS_CERT:-}" ]; then
    echo "  Certificate:    self-signed, SHA-256 fingerprint $(cert_fingerprint "$ASSAYR_DIR/certs/tls.crt")"
    echo "                  Browsers warn about it until you replace it with one from your certificate authority."
  fi
  echo
  echo "Next steps:"
  echo "  - Back up regularly: $sudo$ASSAYR_DIR/assayr backup"
  if [ "$1" = https ]; then
    echo "  - To use your own certificate, replace tls.crt and tls.key in $ASSAYR_DIR/certs, then run: $sudo$ASSAYR_DIR/assayr restart"
  fi
  echo "  - Status and logs: $sudo$ASSAYR_DIR/assayr status, $sudo$ASSAYR_DIR/assayr logs"
}
