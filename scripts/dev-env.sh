#!/usr/bin/env bash
# Source this before running uv, npm or python: keeps caches, Python installs and temp
# files inside the repo (the dev machine's C: drive has no free space).
_ASSAYR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then _ASSAYR_ROOT="$(cygpath -m "$_ASSAYR_ROOT")"; fi
export UV_CACHE_DIR="$_ASSAYR_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$_ASSAYR_ROOT/.cache/python"
export npm_config_cache="$_ASSAYR_ROOT/.cache/npm"
export TMPDIR="$_ASSAYR_ROOT/.cache/tmp" TMP="$_ASSAYR_ROOT/.cache/tmp" TEMP="$_ASSAYR_ROOT/.cache/tmp"
mkdir -p "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR" "$npm_config_cache" "$TMPDIR"
