"""TLS certificate helpers for installers: self-signed generation, PFX import, key/cert check."""

import datetime as dt
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


class CertError(Exception):
    pass


def _write_pair(cert_pem: bytes, key_pem: bytes, cert_path: Path, key_path: Path) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)


def _key_pem(key) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _public_pem(key) -> bytes:
    return key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def generate_self_signed(hostname: str, cert_path: Path, key_path: Path, days: int = 730) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = dt.datetime.now(dt.UTC)
    names = [x509.DNSName(hostname)] + ([x509.DNSName("localhost")] if hostname != "localhost" else [])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    _write_pair(cert.public_bytes(serialization.Encoding.PEM), _key_pem(key), cert_path, key_path)


def pfx_to_pem(pfx: bytes, password: str | None, cert_path: Path, key_path: Path) -> None:
    try:
        key, cert, extra = pkcs12.load_key_and_certificates(pfx, password.encode() if password else None)
    except ValueError as exc:
        raise CertError("The .pfx file could not be opened: check the password.") from exc
    if key is None or cert is None:
        raise CertError("The .pfx file must contain both the certificate and its private key.")
    chain = b"".join(c.public_bytes(serialization.Encoding.PEM) for c in [cert, *(extra or [])])
    _write_pair(chain, _key_pem(key), cert_path, key_path)


def check_pair(cert_path: Path, key_path: Path) -> None:
    try:
        cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
        key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    except (OSError, ValueError) as exc:
        raise CertError(f"The certificate or key can't be read: {exc}") from exc
    if _public_pem(cert.public_key()) != _public_pem(key.public_key()):
        raise CertError("The private key does not match the certificate.")
