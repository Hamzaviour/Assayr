# shellcheck shell=bash
# Reading and writing assayr.env (KEY=value lines; no quoting, no variables).

# env_get KEY FILE — the value of the last KEY= line, or nothing.
env_get() {
  [ -f "$2" ] || return 0
  { grep -E "^$1=" "$2" || true; } | tail -n 1 | cut -d= -f2-
}

# env_set KEY VALUE FILE — replace or add KEY; the file stays owner-only.
env_set() {
  local key="$1" value="$2" file="$3" tmp
  tmp="$(mktemp "$file.XXXXXX")"
  if [ -f "$file" ]; then
    awk -v k="$key=" 'index($0, k) != 1' "$file" >"$tmp"
  fi
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$file"
}

# env_merge_defaults EXAMPLE FILE — add settings that exist in EXAMPLE but not in FILE, with
# their default values; existing values never change. Prints the added keys.
env_merge_defaults() {
  local example="$1" file="$2" line key added=""
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in '' | '#'*) continue ;; esac
    key="${line%%=*}"
    if ! grep -qE "^$key=" "$file"; then
      printf '%s\n' "$line" >>"$file"
      added="$added $key"
    fi
  done <"$example"
  echo "${added# }"
}

# random_password — 32 random letters and digits.
random_password() {
  local chars=""
  while [ "${#chars}" -lt 32 ]; do
    chars="$chars$(head -c 256 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9')"
  done
  printf '%s\n' "${chars:0:32}"
}
