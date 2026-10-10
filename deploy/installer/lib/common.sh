# shellcheck shell=bash
# Messages, the install log, prompts and input checks shared by every command.

ASSAYR_LOG="${ASSAYR_LOG:-}"
ASSAYR_INTERACTIVE="${ASSAYR_INTERACTIVE:-1}"
ASSAYR_ASSUME_YES="${ASSAYR_ASSUME_YES:-0}"
ASSAYR_RETRY_HINT="${ASSAYR_RETRY_HINT:-}"

_log_line() {
  [ -n "$ASSAYR_LOG" ] || return 0
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$ASSAYR_LOG" 2>/dev/null || true
}

info() {
  printf '==> %s\n' "$*"
  _log_line "INFO $*"
}

warn() {
  printf 'Warning: %s\n' "$*" >&2
  _log_line "WARN $*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  _log_line "ERROR $*"
  if [ -n "$ASSAYR_RETRY_HINT" ]; then printf '%s\n' "$ASSAYR_RETRY_HINT" >&2; fi
  if [ -n "$ASSAYR_LOG" ]; then printf 'Details: %s\n' "$ASSAYR_LOG" >&2; fi
  exit 1
}

# log_to FILE — from now on, record every step and command output in FILE (owner-only).
log_to() {
  ASSAYR_LOG="$1"
  (umask 077 && : >>"$ASSAYR_LOG")
}

# run_logged CMD... — run a command with all its output going to the log only.
# The command line itself is logged: never pass a secret as an argument.
run_logged() {
  _log_line "RUN $*"
  if [ -n "$ASSAYR_LOG" ]; then
    "$@" >>"$ASSAYR_LOG" 2>&1
  else
    "$@" >/dev/null 2>&1
  fi
}

# need_value OPTION VALUE — stop when an option that takes a value didn't get one.
need_value() {
  if [ -z "${2:-}" ] || [ "${2#--}" != "${2:-}" ]; then die "$1 needs a value."; fi
}

# ask VAR QUESTION [DEFAULT] [optional]
# Keeps VAR when it is already set (from an option or the environment). Without questions
# (--non-interactive) it takes DEFAULT, and fails when a required value has no default.
ask() {
  local var="$1" question="$2" default="${3:-}" optional="${4:-}" answer=""
  if [ -n "${!var:-}" ]; then return 0; fi
  if [ "$ASSAYR_INTERACTIVE" != 1 ]; then
    if [ -z "$default" ] && [ "$optional" != optional ]; then die "Set $var when using --non-interactive."; fi
    printf -v "$var" '%s' "$default"
    return 0
  fi
  while :; do
    if [ -n "$default" ]; then
      read -r -p "$question [$default]: " answer || true
    else
      read -r -p "$question: " answer || true
    fi
    answer="${answer:-$default}"
    if [ -n "$answer" ] || [ "$optional" = optional ]; then break; fi
    echo "This is required."
  done
  printf -v "$var" '%s' "$answer"
}

password_problem() {
  if [ "${#1}" -lt 12 ]; then echo "The password must be at least 12 characters."; fi
}

# ask_password VAR — the administrator password: checked when given, otherwise typed twice, hidden.
ask_password() {
  local var="$1" first="" second="" problem
  if [ -n "${!var:-}" ]; then
    problem="$(password_problem "${!var}")"
    [ -z "$problem" ] || die "$problem"
    return 0
  fi
  [ "$ASSAYR_INTERACTIVE" = 1 ] || die "Set $var when using --non-interactive."
  while :; do
    read -r -s -p "Administrator password (at least 12 characters): " first || true
    echo
    problem="$(password_problem "$first")"
    if [ -n "$problem" ]; then
      echo "$problem"
      continue
    fi
    read -r -s -p "Type it again: " second || true
    echo
    if [ "$first" != "$second" ]; then
      echo "The passwords don't match."
      continue
    fi
    printf -v "$var" '%s' "$first"
    return 0
  done
}

# confirm_word WORD MESSAGE — explain, then require WORD to be typed (or --yes).
confirm_word() {
  local word="$1" answer=""
  printf '%s\n' "$2"
  if [ "$ASSAYR_ASSUME_YES" = 1 ]; then return 0; fi
  [ "$ASSAYR_INTERACTIVE" = 1 ] || die "Add --yes to confirm when running without questions."
  read -r -p "Type $word to continue: " answer || true
  [ "$answer" = "$word" ] || die "Cancelled; nothing was changed."
}

# text_problem LABEL VALUE — refuse values that would break assayr.env.
text_problem() {
  case "$2" in
    '') echo "$1 can't be empty." ;;
    *[\$\"\'\`\\#]* | *$'\n'*) echo "$1 can't contain \$, quotes, backticks, backslashes or #." ;;
  esac
}

hostname_problem() {
  local pattern='^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$'
  [[ "$1" =~ $pattern ]] || echo "\"$1\" isn't a valid hostname. Use letters, digits, dots and hyphens, for example grc.example.local."
}

email_problem() {
  local pattern='^[^@[:space:]]+@[^@[:space:]]+$'
  [[ "$1" =~ $pattern ]] || echo "\"$1\" isn't a valid email address."
}

port_problem() {
  local pattern='^[0-9]+$'
  if [[ "$1" =~ $pattern ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]; then return 0; fi
  echo "\"$1\" isn't a valid port. Use a number from 1 to 65535."
}
