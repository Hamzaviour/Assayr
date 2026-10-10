# shellcheck shell=bash
# The self-signed certificate used when the customer doesn't supply one.

# make_self_signed HOST CERT KEY — RSA 3072, 825 days, valid for HOST, localhost and 127.0.0.1.
make_self_signed() {
  local host="$1" cert="$2" key="$3" conf first
  local ip_pattern='^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
  if [[ "$host" =~ $ip_pattern ]]; then first="IP.1 = $host"; else first="DNS.1 = $host"; fi
  conf="$(mktemp "${TMPDIR:-/tmp}/assayr-cert.XXXXXX")"
  cat >"$conf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $host
O = Assayr self-signed
[ext]
subjectAltName = @alt
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
[alt]
$first
DNS.2 = localhost
IP.2 = 127.0.0.1
EOF
  if ! (umask 077 && openssl req -x509 -newkey rsa:3072 -nodes -days 825 -config "$conf" \
    -keyout "$key" -out "$cert" >/dev/null 2>&1); then
    rm -f "$conf"
    return 1
  fi
  rm -f "$conf"
  chmod 600 "$key"
  chmod 644 "$cert"
}

cert_fingerprint() {
  openssl x509 -noout -fingerprint -sha256 -in "$1" | cut -d= -f2
}
