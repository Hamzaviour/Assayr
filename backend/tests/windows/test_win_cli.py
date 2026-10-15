import json

from typer.testing import CliRunner

from assayr.cli import app
from assayr.windows import cli as wincli
from assayr.windows.layout import InstallConfig

runner = CliRunner()


def saved_config(tmp_path):
    c = InstallConfig(tmp_path / "p", tmp_path / "d", "h", "o", version="0.3.0")
    c.backups_dir.mkdir(parents=True)
    c.save()
    return c


def test_install_reads_answers_and_env_password(tmp_path, monkeypatch):
    seen = {}

    def fake_install(cfg, email, password, cert, run, **kw):
        seen.update(cfg=cfg, email=email, password=password, cert=cert)

    monkeypatch.setattr(wincli.provision, "install", fake_install)
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps(
            {
                "install_dir": str(tmp_path / "p"),
                "data_dir": str(tmp_path / "d"),
                "hostname": "h",
                "org_name": "Acme",
                "https_port": 443,
                "http_port": 80,
                "web_mode": "https",
                "behind_tls_proxy": False,
                "malware_scan": True,
                "version": "0.3.0",
                "admin_email": "a@b.c",
                "cert_mode": "self-signed",
                "cert_file": "",
                "key_file": "",
            }
        )
    )
    result = runner.invoke(
        app,
        ["win", "install", "--answers", str(answers)],
        env={"ASSAYR_ADMIN_PASSWORD": "a-very-long-password"},
    )
    assert result.exit_code == 0, result.output
    assert seen["email"] == "a@b.c" and seen["password"] == "a-very-long-password"
    assert seen["cfg"].org_name == "Acme" and seen["cert"].mode == "self-signed"


def test_install_without_password_fails(tmp_path):
    answers = tmp_path / "a.json"
    answers.write_text("{}")
    result = runner.invoke(
        app, ["win", "install", "--answers", str(answers)], env={"ASSAYR_ADMIN_PASSWORD": ""}
    )
    assert result.exit_code == 1 and "ASSAYR_ADMIN_PASSWORD" in result.output


def test_status_prints_each_service(tmp_path, monkeypatch):
    c = saved_config(tmp_path)
    monkeypatch.setattr(
        wincli.services, "status", lambda cfg, r: {"AssayrDb": "RUNNING", "AssayrApi": "STOPPED"}
    )
    result = runner.invoke(app, ["win", "status", "--data-dir", str(c.data_dir)])
    assert result.exit_code == 0, result.output
    assert "Assayr 0.3.0" in result.output and "AssayrDb" in result.output and "STOPPED" in result.output


def test_missing_install_is_a_clear_error(tmp_path):
    result = runner.invoke(app, ["win", "status", "--data-dir", str(tmp_path / "nowhere")])
    assert result.exit_code == 1 and "No Assayr installation" in result.output


def test_scheduled_backup_prunes_to_14_and_keeps_manual(tmp_path, monkeypatch):
    c = saved_config(tmp_path)
    for i in range(16):
        (c.backups_dir / f"assayr-0.3.0-202610{i + 1:02d}T020000Z-scheduled.tar.gz").write_bytes(b"x")
    (c.backups_dir / "assayr-0.3.0-20260101T000000Z.tar.gz").write_bytes(b"manual")

    def fake_backup(cfg, r, now=None):
        p = cfg.backups_dir / "assayr-0.3.0-20261031T020000Z.tar.gz"
        p.write_bytes(b"new")
        return p

    monkeypatch.setattr(wincli.provision, "make_backup", fake_backup)
    result = runner.invoke(app, ["win", "backup", "--scheduled", "--data-dir", str(c.data_dir)])
    assert result.exit_code == 0, result.output
    kept = sorted(p.name for p in c.backups_dir.glob("*-scheduled.tar.gz"))
    assert len(kept) == 14 and kept[-1] == "assayr-0.3.0-20261031T020000Z-scheduled.tar.gz"
    assert (c.backups_dir / "assayr-0.3.0-20260101T000000Z.tar.gz").exists()


def test_restore_refuses_newer_backup(tmp_path, monkeypatch):
    c = saved_config(tmp_path)

    class Source:
        version, created, folder = "0.9.0", "x", tmp_path

    monkeypatch.setattr(wincli, "read_backup", lambda f, w: Source())
    result = runner.invoke(
        app, ["win", "restore", str(tmp_path / "b.tar.gz"), "--yes", "--data-dir", str(c.data_dir)]
    )
    assert result.exit_code == 1 and "newer than the installed 0.3.0" in result.output


def test_logs_rejects_unknown_service(tmp_path):
    c = saved_config(tmp_path)
    result = runner.invoke(app, ["win", "logs", "nope", "--data-dir", str(c.data_dir)])
    assert result.exit_code == 1 and "Choose one of" in result.output
