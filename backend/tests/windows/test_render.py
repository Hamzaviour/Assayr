import io
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values

from assayr.config import get_settings
from assayr.windows.layout import InstallConfig
from assayr.windows.render import (
    render_caddyfile,
    render_clamd_conf,
    render_env,
    render_service_xml,
)

PW = 'a "quoted" p%ss & ^word'


def cfg(tmp_path, **kw):
    return InstallConfig(
        install_dir=tmp_path / "Program Files" / "Assayr",
        data_dir=tmp_path / "Assayr Data",
        hostname="grc.example.local",
        org_name='Acme "Bank" & Co',
        version="0.3.0",
        **kw,
    )


def parse_env(text):
    return dotenv_values(stream=io.StringIO(text))


def test_env_round_trips_awkward_values(tmp_path):
    c = cfg(tmp_path)
    values = parse_env(render_env(c, PW))
    assert values["ASSAYR_ORG_NAME"] == 'Acme "Bank" & Co'
    assert values["POSTGRES_PASSWORD"] == PW
    url = urlsplit(values["ASSAYR_DATABASE_URL"].replace("postgresql+pg8000", "postgresql"))
    assert unquote(url.password) == PW and url.port == 5432
    assert values["ASSAYR_STORAGE_DIR"] == str(c.blobs_dir)
    assert values["ASSAYR_CLAMAV_HOST"] == "127.0.0.1"
    assert values["ASSAYR_SECURE_COOKIES"] == "true"


def test_env_without_scan_has_no_clamav(tmp_path):
    assert parse_env(render_env(cfg(tmp_path, malware_scan=False), "x"))["ASSAYR_CLAMAV_HOST"] == ""


def test_http_mode_cookies(tmp_path):
    assert parse_env(render_env(cfg(tmp_path, web_mode="http"), "x"))["ASSAYR_SECURE_COOKIES"] == "false"
    behind = cfg(tmp_path, web_mode="http", behind_tls_proxy=True)
    assert parse_env(render_env(behind, "x"))["ASSAYR_SECURE_COOKIES"] == "true"


def test_rendered_env_loads_into_settings(tmp_path, monkeypatch):
    c = cfg(tmp_path)
    c.data_dir.mkdir(parents=True)
    c.env_file.write_text(render_env(c, PW), encoding="utf-8")
    monkeypatch.setenv("ASSAYR_ENV_FILE", str(c.env_file))
    for k in ("ASSAYR_DATABASE_URL", "ASSAYR_ORG_NAME", "ASSAYR_STORAGE_DIR"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.org_name == 'Acme "Bank" & Co' and s.storage_dir == str(c.blobs_dir)
    finally:
        get_settings.cache_clear()


def test_caddyfile_https(tmp_path):
    c = cfg(tmp_path, https_port=8443, http_port=8080)
    text = render_caddyfile(c)
    assert ":8443 {" in text and ":8080 {" in text
    assert f'tls "{(c.certs_dir / "tls.crt").as_posix()}" "{(c.certs_dir / "tls.key").as_posix()}"' in text
    assert "redir https://{host}:8443{uri} permanent" in text
    assert "reverse_proxy 127.0.0.1:8000" in text
    assert f'root * "{c.web_root.as_posix()}"' in text
    assert "Content-Security-Policy" in text and "admin off" in text


def test_caddyfile_http_only(tmp_path):
    text = render_caddyfile(cfg(tmp_path, web_mode="http", http_port=8080))
    assert ":8080 {" in text and "tls " not in text and "redir" not in text


def test_clamd_conf(tmp_path):
    c = cfg(tmp_path)
    text = render_clamd_conf(c)
    assert "TCPSocket 3310" in text and "TCPAddr 127.0.0.1" in text
    assert f'DatabaseDirectory "{c.clamav_db_dir}"' in text


def test_service_xml_quotes_paths_and_sets_env_file(tmp_path):
    c = cfg(tmp_path)
    root = ET.fromstring(render_service_xml(c, "AssayrApi"))
    assert root.findtext("id") == "AssayrApi"
    assert root.findtext("executable") == str(c.python_exe)
    assert "-m uvicorn assayr.main:create_app --factory --host 127.0.0.1 --port 8000" in root.findtext(
        "arguments"
    )
    envs = {e.get("name"): e.get("value") for e in root.findall("env")}
    assert envs["ASSAYR_ENV_FILE"] == str(c.env_file)
    assert [d.text for d in root.findall("depend")] == ["AssayrDb"]
    assert root.findtext("startmode") == "Automatic"
    assert root.find("onfailure") is not None
    assert root.findtext("logpath") == str(c.logs_dir)


def test_db_service(tmp_path):
    c = cfg(tmp_path)
    args = ET.fromstring(render_service_xml(c, "AssayrDb")).findtext("arguments")
    assert ET.fromstring(render_service_xml(c, "AssayrDb")).findtext("executable") == str(
        c.pg_bin / "postgres.exe"
    )
    assert f'-D "{c.db_dir}"' in args and "-p 5432" in args


def test_worker_depends_on_clamav_only_when_scanning(tmp_path):
    with_scan = ET.fromstring(render_service_xml(cfg(tmp_path), "AssayrWorker"))
    without = ET.fromstring(render_service_xml(cfg(tmp_path, malware_scan=False), "AssayrWorker"))
    assert [d.text for d in with_scan.findall("depend")] == ["AssayrDb", "AssayrClamAV"]
    assert [d.text for d in without.findall("depend")] == ["AssayrDb"]
