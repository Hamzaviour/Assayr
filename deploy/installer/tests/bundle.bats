setup() {
  load helpers
  load_libs
  B="$BATS_TEST_TMPDIR/bundle"
  mkdir -p "$B/lib" "$B/images"
  echo "#!/usr/bin/env bash" >"$B/assayr"
  echo "lib" >"$B/lib/main.sh"
  echo "image" >"$B/images/api.tar"
  echo "1.2.3" >"$B/VERSION"
}

@test "a bundle with intact files passes the checksum check" {
  write_sums "$B"
  [ "$(grep -c . "$B/SHA256SUMS")" -eq 4 ]
  run verify_bundle "$B"
  [ "$status" -eq 0 ]
}

@test "a changed file is reported" {
  write_sums "$B"
  echo "tampered" >>"$B/lib/main.sh"
  run verify_bundle "$B"
  [ "$status" -eq 1 ]
  [ "$output" = "./lib/main.sh does not match its checksum." ]
}

@test "a missing file and a missing checksum list are reported" {
  write_sums "$B"
  rm "$B/images/api.tar"
  run verify_bundle "$B"
  [ "$status" -eq 1 ]
  [ "$output" = "./images/api.tar is missing." ]
  rm "$B/SHA256SUMS"
  run verify_bundle "$B"
  [ "$output" = "SHA256SUMS is missing." ]
}

@test "bundle_value reads VERSION without whitespace" {
  printf ' 1.2.3 \n' >"$B/VERSION"
  [ "$(bundle_value "$B" VERSION)" = 1.2.3 ]
}

@test "version_gt compares versions number by number" {
  version_gt 1.10.0 1.9.9
  version_gt 2.0.0 1.99.99
  version_gt 0.2.1 0.2.0
  version_gt 2.29.2-desktop.2 2.17.0
  # bats ignores a failing "! cmd", so negative cases use run !
  run ! version_gt 0.2.0 0.2.0
  run ! version_gt 0.1.9 0.2.0
}

@test "version_valid accepts MAJOR.MINOR.PATCH only" {
  version_valid 0.2.0
  version_valid 10.20.30
  run ! version_valid v0.2.0
  run ! version_valid 0.2
  run ! version_valid 0.2.0-rc1
}

@test "copy_program_files copies the program, replaces old library files and skips missing items" {
  local dest="$BATS_TEST_TMPDIR/install"
  mkdir -p "$dest/lib"
  echo "stale" >"$dest/lib/removed-in-new-version.sh"
  echo "amd64" >"$B/ARCH"
  copy_program_files "$B" "$dest"
  [ -f "$dest/assayr" ]
  [ -f "$dest/lib/main.sh" ]
  [ -f "$dest/ARCH" ]
  [ ! -e "$dest/lib/removed-in-new-version.sh" ]
  [ ! -e "$dest/VERSION" ]
  [ ! -e "$dest/images" ]
}
