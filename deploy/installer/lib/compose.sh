# shellcheck shell=bash
# docker compose for the installation in $ASSAYR_DIR, and what we ask of the running stack.

ASSAYR_DIR="${ASSAYR_DIR:-}"

assayr_compose() {
  local env="$ASSAYR_DIR/assayr.env"
  local args=(compose --project-directory "$ASSAYR_DIR" --env-file "$env" -f "$ASSAYR_DIR/compose.yaml")
  if [ "$(env_get ASSAYR_WEB_MODE "$env")" = https ]; then args+=(-f "$ASSAYR_DIR/compose.https.yaml"); fi
  if [ "$(env_get ASSAYR_MALWARE_SCAN "$env")" = true ]; then args+=(--profile av); fi
  docker "${args[@]}" "$@"
}

wait_timeout() {
  local seconds
  seconds="$(env_get ASSAYR_WAIT_TIMEOUT "$ASSAYR_DIR/assayr.env")"
  echo "${seconds:-600}"
}

# start_stack — start every service and wait until all are healthy.
start_stack() {
  run_logged assayr_compose up -d --wait --wait-timeout "$(wait_timeout)"
}

api_ready() {
  run_logged assayr_compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/readyz', timeout=5)"
}

# audit_ok — the audit trail's hash chain is intact.
audit_ok() {
  run_logged assayr_compose exec -T api assayr audit-verify
}

install_url() {
  local env="$ASSAYR_DIR/assayr.env" host port
  host="$(env_get ASSAYR_HOSTNAME "$env")"
  if [ "$(env_get ASSAYR_WEB_MODE "$env")" = https ]; then
    port="$(env_get ASSAYR_HTTPS_PORT "$env")"
    if [ "$port" = 443 ]; then echo "https://$host"; else echo "https://$host:$port"; fi
  else
    port="$(env_get ASSAYR_HTTP_PORT "$env")"
    if [ "$port" = 80 ]; then echo "http://$host"; else echo "http://$host:$port"; fi
  fi
}

# create_admin_account EMAIL PASSWORD — the password reaches the container through the
# environment (docker compose exec -e NAME forwards it), never on a command line.
create_admin_account() {
  (
    export ASSAYR_ADMIN_PASSWORD="$2"
    run_logged assayr_compose exec -T -e ASSAYR_ADMIN_PASSWORD api \
      assayr create-admin --email "$1" --full-name Administrator
  )
}
