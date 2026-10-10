setup() {
  load helpers
  load_libs
  export ASSAYR_PROC_VERSION="$BATS_TEST_TMPDIR/version"
  echo "Linux version 6.8.0 (buildd@lcy02)" >"$ASSAYR_PROC_VERSION"
}

@test "detect_platform tells Linux, WSL and macOS apart" {
  ASSAYR_UNAME_S=Linux run detect_platform
  [ "$output" = linux ]
  echo "Linux version 5.15.153.1-microsoft-standard-WSL2" >"$ASSAYR_PROC_VERSION"
  ASSAYR_UNAME_S=Linux run detect_platform
  [ "$output" = wsl ]
  ASSAYR_UNAME_S=Darwin run detect_platform
  [ "$output" = macos ]
  ASSAYR_UNAME_S=MINGW64_NT-10.0 run detect_platform
  [ "$output" = unsupported ]
}

@test "normalize_arch maps Docker and uname names" {
  [ "$(normalize_arch x86_64)" = amd64 ]
  [ "$(normalize_arch amd64)" = amd64 ]
  [ "$(normalize_arch aarch64)" = arm64 ]
  [ "$(normalize_arch arm64)" = arm64 ]
  run normalize_arch ppc64le
  [ "$status" -eq 1 ]
}

@test "Linux installs in /opt/assayr, evaluation platforms in the home folder" {
  [ "$(default_install_dir linux)" = /opt/assayr ]
  [ "$(HOME=/home/sana default_install_dir macos)" = /home/sana/assayr ]
  [ "$(HOME=/home/sana default_install_dir wsl)" = /home/sana/assayr ]
  [ "$(default_hostname macos)" = localhost ]
}

@test "Linux needs root; macOS and WSL don't" {
  ASSAYR_EUID=1000 run require_privileges linux install
  [ "$status" -eq 1 ]
  [[ "$output" == *"Run this as root, for example: sudo ./assayr install"* ]]
  ASSAYR_EUID=0 run require_privileges linux install
  [ "$status" -eq 0 ]
  ASSAYR_EUID=501 run require_privileges macos install
  [ "$status" -eq 0 ]
}

@test "macOS and WSL are told the setup is for evaluation" {
  run evaluation_notice macos
  [[ "$output" == *"for evaluation"* ]]
  run evaluation_notice linux
  [ -z "$output" ]
}
