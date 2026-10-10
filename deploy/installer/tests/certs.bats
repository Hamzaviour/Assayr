setup() {
  load helpers
  load_libs
  command -v openssl >/dev/null 2>&1 || skip "openssl isn't installed"
  CERT="$BATS_TEST_TMPDIR/tls.crt"
  KEY="$BATS_TEST_TMPDIR/tls.key"
}

@test "the self-signed certificate covers the hostname, localhost and 127.0.0.1" {
  make_self_signed grc.corp.local "$CERT" "$KEY"
  run openssl x509 -in "$CERT" -noout -text
  [[ "$output" == *"DNS:grc.corp.local"* ]]
  [[ "$output" == *"DNS:localhost"* ]]
  [[ "$output" == *"IP Address:127.0.0.1"* ]]
}

@test "an IP address as hostname becomes an IP entry" {
  make_self_signed 10.20.30.40 "$CERT" "$KEY"
  run openssl x509 -in "$CERT" -noout -text
  [[ "$output" == *"IP Address:10.20.30.40"* ]]
}

@test "the fingerprint is a SHA-256 in colon-separated hex" {
  make_self_signed localhost "$CERT" "$KEY"
  [[ "$(cert_fingerprint "$CERT")" =~ ^([0-9A-F]{2}:){31}[0-9A-F]{2}$ ]]
}

@test "the private key is readable by the owner only" {
  skip_on_windows
  make_self_signed localhost "$CERT" "$KEY"
  [ "$(file_mode "$KEY")" = "rw-------" ]
}
