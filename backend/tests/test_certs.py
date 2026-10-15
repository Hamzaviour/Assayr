import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from typer.testing import CliRunner

from assayr.certs import CertError, check_pair, generate_self_signed, pfx_to_pem
from assayr.cli import app


def test_self_signed_has_hostname_and_localhost(tmp_path):
    crt, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    generate_self_signed("grc.example.local", crt, key)
    cert = x509.load_pem_x509_certificate(crt.read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert set(names.get_values_for_type(x509.DNSName)) == {"grc.example.local", "localhost"}
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days >= 729
    check_pair(crt, key)


def _pfx(password: bytes | None) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "grc")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    enc = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
    return pkcs12.serialize_key_and_certificates(b"grc", key, cert, None, enc)


def test_pfx_with_password_converts(tmp_path):
    crt, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    pfx_to_pem(_pfx(b"p&ss %word^"), "p&ss %word^", crt, key)
    check_pair(crt, key)


def test_pfx_wrong_password_is_readable_error(tmp_path):
    with pytest.raises(CertError, match="password"):
        pfx_to_pem(_pfx(b"right"), "wrong", tmp_path / "c", tmp_path / "k")


def test_mismatched_pair_rejected(tmp_path):
    generate_self_signed("a", tmp_path / "a.crt", tmp_path / "a.key")
    generate_self_signed("b", tmp_path / "b.crt", tmp_path / "b.key")
    with pytest.raises(CertError, match="does not match"):
        check_pair(tmp_path / "a.crt", tmp_path / "b.key")


def test_cli_import_pfx_reads_password_from_environment(tmp_path):
    pfx = tmp_path / "server.pfx"
    pfx.write_bytes(_pfx(b"secret"))
    result = CliRunner().invoke(
        app, ["import-pfx", str(pfx), "--out", str(tmp_path / "certs")], env={"ASSAYR_PFX_PASSWORD": "secret"}
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "certs" / "tls.crt").exists() and (tmp_path / "certs" / "tls.key").exists()
