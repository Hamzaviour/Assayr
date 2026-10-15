from assayr.windows.layout import InstallConfig, active_services


def cfg(tmp_path, **kw):
    return InstallConfig(
        install_dir=tmp_path / "Program Files" / "Assayr",
        data_dir=tmp_path / "Assayr Data",
        hostname="grc.example.local",
        org_name="Acme & Sons",
        **kw,
    )


def test_round_trip(tmp_path):
    c = cfg(tmp_path, https_port=8443, version="0.3.0")
    c.data_dir.mkdir(parents=True)
    c.save()
    assert InstallConfig.load(c.data_dir) == c


def test_paths(tmp_path):
    c = cfg(tmp_path)
    assert c.python_exe == c.install_dir / "python" / "python.exe"
    assert c.pg_bin == c.install_dir / "pgsql" / "bin"
    assert c.env_file == c.data_dir / "assayr.env"
    assert c.health_url == "https://localhost:443/api/v1/healthz"
    assert cfg(tmp_path, web_mode="http", http_port=8080).health_url == "http://localhost:8080/api/v1/healthz"


def test_services_without_scan(tmp_path):
    assert "AssayrClamAV" not in active_services(cfg(tmp_path, malware_scan=False))
    assert active_services(cfg(tmp_path))[0] == "AssayrDb"
