# shellcheck shell=bash
# Bundle integrity, versions, program files and image loading.

# What an installation keeps from a bundle. VERSION is handled separately (written last on upgrade).
PROGRAM_FILES="assayr lib compose.yaml compose.https.yaml assayr.env.example README-INSTALL.md ARCH"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

# write_sums DIR — write DIR/SHA256SUMS covering every other file under DIR.
write_sums() {
  (
    cd "$1"
    find . -type f ! -name 'SHA256SUMS*' | LC_ALL=C sort | while IFS= read -r file; do
      printf '%s  %s\n' "$(sha256_of "$file")" "$file"
    done >SHA256SUMS.tmp
    mv SHA256SUMS.tmp SHA256SUMS
  )
}

# verify_bundle DIR — every file listed in DIR/SHA256SUMS exists and matches. Prints the first
# problem and returns 1.
verify_bundle() {
  local dir="$1" sum path
  if [ ! -f "$dir/SHA256SUMS" ]; then
    echo "SHA256SUMS is missing."
    return 1
  fi
  while read -r sum path; do
    [ -n "$sum" ] || continue
    path="${path#\*}"
    if [ ! -f "$dir/$path" ]; then
      echo "$path is missing."
      return 1
    fi
    if [ "$(sha256_of "$dir/$path")" != "$sum" ]; then
      echo "$path does not match its checksum."
      return 1
    fi
  done <"$dir/SHA256SUMS"
}

# bundle_value DIR NAME — the content of DIR/NAME (VERSION, ARCH) without whitespace.
bundle_value() {
  [ -f "$1/$2" ] || return 1
  tr -d '[:space:]' <"$1/$2"
}

version_valid() {
  local pattern='^[0-9]+\.[0-9]+\.[0-9]+$'
  [[ "$1" =~ $pattern ]]
}

# version_gt A B — true when A is newer than B (numbers compared part by part; suffixes such
# as "-desktop.2" are ignored).
version_gt() {
  local a="${1#v}" b="${2#v}" i x y
  for i in 1 2 3; do
    x="$(printf '%s' "$a" | cut -d. -f"$i")"
    y="$(printf '%s' "$b" | cut -d. -f"$i")"
    x="${x%%[!0-9]*}"
    y="${y%%[!0-9]*}"
    x="${x:-0}"
    y="${y:-0}"
    if [ "$x" -gt "$y" ]; then return 0; fi
    if [ "$x" -lt "$y" ]; then return 1; fi
  done
  return 1
}

# copy_program_files SRC DEST — replace DEST's program files with SRC's.
copy_program_files() {
  local src="$1" dest="$2" item
  # shellcheck disable=SC2086 # PROGRAM_FILES is a word list
  for item in $PROGRAM_FILES; do
    [ -e "$src/$item" ] || continue
    rm -rf "${dest:?}/$item"
    cp -R "$src/$item" "$dest/$item"
  done
}

# load_images BUNDLE — docker load every image listed in images/IMAGES.txt that isn't loaded yet.
load_images() {
  local bundle="$1" file ref
  while read -r file ref _; do
    [ -n "$file" ] || continue
    if docker image inspect "$ref" >/dev/null 2>&1; then
      info "Image $ref is already loaded"
    else
      info "Loading image $ref"
      run_logged docker load -i "$bundle/images/$file" || return 1
    fi
  done <"$bundle/images/IMAGES.txt"
}
