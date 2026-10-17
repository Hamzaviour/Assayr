import subprocess

import pytest
from dotenv import dotenv_values

from assayr.windows import provision
from assayr.windows.layout import InstallConfig
from assayr.windows.provision import CertChoice, ProvisionError


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(provision.services, "wait_running", lambda *a, **k: None)
    monkeypatch.setattr(provision, "_sleep", lambda s: None)


class FakeRunner:
    def __init__(self, fail_on=None, not_ready=0, createdb_err=None, whoami=""):
        self.calls, self.envs, self.fail_on = [], [], fail_on
        self.not_ready, self.createdb_err, self.whoami = not_ready, createdb_err, whoami

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self.calls.append(args)
        self.envs.append(env or {})
        if self.fail_on and any(self.fail_on in a for a in args):
            if check:
                raise provision.CommandError(f"{args[0]} {self.fail_on} failed")
            return subprocess.CompletedProcess(args, 1, "", "boom")
        if args[0].endswith("pg_isready.exe") and self.not_ready:
            self.not_ready -= 1
            return subprocess.CompletedProcess(args, 2, "", "no response")
        if args[0].endswith("createdb.exe") and self.createdb_err:
            return subprocess.CompletedProcess(args, 1, "", self.createdb_err)
        if args[0] == "whoami":
            return subprocess.CompletedProcess(args, 0, self.whoami, "")
        return subprocess.CompletedProcess(args, 0, "", "")


def make_cfg(tmp_path, **kw):
    c = InstallConfig(
        tmp_path / "Program Files" / "Assayr",
        tmp_path / "Assayr Data",
        "grc.local",
        "Acme",
        version="0.3.0",
        **kw,
    )
    c.services_dir.mkdir(parents=True, exist_ok=True)
    (c.services_dir / "WinSW-x64.exe").write_bytes(b"MZ")
    c.bundled_signatures.mkdir(parents=True, exist_ok=True)
    (c.bundled_signatures / "main.cvd").write_bytes(b"sig")
    return c


def healthy(*args, **kwargs):
    return "0.3.0"


def run_install(tmp_path, runner=None, **kw):
    c = make_cfg(tmp_path, **kw)
    r = runner or FakeRunner()
    provision.install(
        c,
        "admin@acme.com",
        "a-very-long-password",
        CertChoice("self-signed"),
        r,
        wait=healthy,
        token=lambda n: 'pw"with%odd&chars',
    )
    return c, r


def flat(r):
    return [" ".join(c) for c in r.calls]


def test_install_order(tmp_path):
    c, r = run_install(tmp_path)
    cmds = flat(r)

    def idx(fragment):
        return next(i for i, cmd in enumerate(cmds) if fragment in cmd)

    assert idx("initdb") < idx("AssayrDb.exe install") < idx("sc.exe start AssayrDb")
    assert idx("sc.exe start AssayrDb") < idx("-m assayr migrate") < idx("-m assayr seed")
    assert idx("-m assayr seed") < idx("-m assayr create-admin") < idx("advfirewall")
    assert idx("advfirewall") < idx("sc.exe start AssayrWeb") < idx("schtasks")
    assert (c.data_dir / "install.json").exists() and (c.certs_dir / "tls.crt").exists()
    assert (c.clamav_db_dir / "main.cvd").exists()


def test_passwords_never_in_arguments(tmp_path):
    c, r = run_install(tmp_path)
    joined = " ".join(flat(r))
    assert "a-very-long-password" not in joined and 'pw"with%odd&chars' not in joined
    admin = next(i for i, cmd in enumerate(r.calls) if "create-admin" in cmd)
    assert r.envs[admin]["ASSAYR_ADMIN_PASSWORD"] == "a-very-long-password"
    initdb = next(i for i, cmd in enumerate(r.calls) if cmd[0].endswith("initdb.exe"))
    assert "--pwfile" in r.calls[initdb]


def test_initdb_pwfile_removed(tmp_path):
    c, _ = run_install(tmp_path)
    assert not list(c.data_dir.glob(".initdb.pw"))


def test_firewall_opens_only_web_ports(tmp_path):
    _, r = run_install(tmp_path, https_port=8443, http_port=8080)
    rules = [c for c in r.calls if "advfirewall" in c and "add" in c]
    assert sorted(next(a for a in c if a.startswith("localport=")) for c in rules) == [
        "localport=8080",
        "localport=8443",
    ]


def test_data_dir_acl(tmp_path):
    _, r = run_install(tmp_path)
    icacls = [c for c in r.calls if c[0] == "icacls.exe"]
    assert any("/inheritance:r" in c for c in icacls)
    assert any(any(a.startswith("NT SERVICE\\AssayrDb:") for a in c) for c in icacls)


def test_failure_on_new_data_dir_cleans_up_and_retry_works(tmp_path):
    r = FakeRunner(fail_on="create-admin")
    with pytest.raises(ProvisionError, match="create-admin"):
        run_install(tmp_path, runner=r)
    assert not (tmp_path / "Assayr Data").exists()
    assert any("AssayrDb.exe uninstall" in cmd for cmd in flat(r))
    run_install(tmp_path)


def test_existing_data_dir_is_kept_on_failure(tmp_path):
    c = make_cfg(tmp_path)
    c.data_dir.mkdir(parents=True)
    (c.data_dir / "keep.txt").write_text("x")
    with pytest.raises(ProvisionError):
        provision.install(
            c,
            "a@b.c",
            "a-very-long-password",
            CertChoice("self-signed"),
            FakeRunner(fail_on="create-admin"),
            wait=healthy,
            token=lambda n: "pw",
        )
    assert (c.data_dir / "keep.txt").exists()


def test_existing_cluster_is_not_reinitialised(tmp_path):
    c = make_cfg(tmp_path)
    c.db_dir.mkdir(parents=True)
    (c.db_dir / "PG_VERSION").write_text("16")
    c.env_file.write_text('POSTGRES_PASSWORD="old"\n')
    r = FakeRunner()
    provision.install(
        c, "a@b.c", "a-very-long-password", CertChoice("self-signed"), r, wait=healthy, token=lambda n: "new"
    )
    assert not any(cmd[0].endswith("initdb.exe") for cmd in r.calls)
    assert 'POSTGRES_PASSWORD="old"' in c.env_file.read_text()


def test_install_creates_a_secret_key(tmp_path):
    c, _ = run_install(tmp_path)
    key = dotenv_values(c.env_file).get("ASSAYR_SECRET_KEY")
    assert key and len(key) >= 32


def test_upgrade_keeps_the_secret_key_or_adds_one(tmp_path):
    c, _ = run_install(tmp_path)
    key = dotenv_values(c.env_file)["ASSAYR_SECRET_KEY"]
    c.version = "0.4.0"
    provision.finish_upgrade(c, FakeRunner(), wait=lambda *a, **k: "0.4.0")
    assert dotenv_values(c.env_file)["ASSAYR_SECRET_KEY"] == key
    old = "\n".join(line for line in c.env_file.read_text().splitlines() if "SECRET_KEY" not in line)
    c.env_file.write_text(old + "\n")
    provision.finish_upgrade(c, FakeRunner(), wait=lambda *a, **k: "0.4.0")
    added = dotenv_values(c.env_file).get("ASSAYR_SECRET_KEY")
    assert added and added != key and dotenv_values(c.env_file)["POSTGRES_PASSWORD"]


def test_uninstall_keeps_data_by_default(tmp_path):
    c, _ = run_install(tmp_path)
    r = FakeRunner()
    provision.uninstall(c, r, delete_data=False)
    assert c.data_dir.exists()
    assert any("advfirewall" in cmd and "delete" in cmd for cmd in flat(r))
    assert any("schtasks" in cmd and "/Delete" in cmd for cmd in flat(r))
    provision.uninstall(c, FakeRunner(), delete_data=True)
    assert not c.data_dir.exists()


def test_finish_upgrade_rerenders_and_migrates(tmp_path):
    c, _ = run_install(tmp_path)
    c.version = "0.4.0"
    r = FakeRunner()
    provision.finish_upgrade(c, r, wait=lambda *a, **k: "0.4.0")
    assert idx_of(r, "-m assayr migrate") < idx_of(r, "-m assayr seed")
    assert "0.4.0" in c.env_file.read_text()
    assert InstallConfig.load(c.data_dir).version == "0.4.0"


def test_finish_upgrade_health_failure_raises(tmp_path):
    c, _ = run_install(tmp_path)

    def unhealthy(*a, **k):
        raise provision.HealthError("down")

    with pytest.raises(ProvisionError, match="down"):
        provision.finish_upgrade(c, FakeRunner(), wait=unhealthy)


def idx_of(r, fragment):
    return next(i for i, cmd in enumerate(flat(r)) if fragment in cmd)


def test_waits_until_postgres_accepts_connections(tmp_path):
    _, r = run_install(tmp_path, runner=FakeRunner(not_ready=3))
    assert sum("pg_isready" in cmd for cmd in flat(r)) == 4
    assert idx_of(r, "pg_isready") < idx_of(r, "createdb") < idx_of(r, "-m assayr migrate")


def test_createdb_already_exists_is_fine(tmp_path):
    run_install(tmp_path, runner=FakeRunner(createdb_err='createdb: error: database "assayr" already exists'))


def test_createdb_other_failure_stops_the_install(tmp_path):
    with pytest.raises(ProvisionError, match="createdb"):
        run_install(tmp_path, runner=FakeRunner(createdb_err="could not connect to server"))


def test_installing_account_is_granted_the_db_folder_before_initdb(tmp_path):
    r = FakeRunner(whoami='"server\\admin","S-1-5-21-111-222-333-500"\n')
    c, _ = run_install(tmp_path, runner=r)
    grant = idx_of(r, "*S-1-5-21-111-222-333-500:(OI)(CI)F")
    assert str(c.db_dir) in r.calls[grant] and grant < idx_of(r, "initdb")


def test_failed_install_keeps_its_log_next_to_the_removed_folder(tmp_path):
    with pytest.raises(ProvisionError, match="Assayr Data-install-failed.log"):
        run_install(tmp_path, runner=FakeRunner(fail_on="create-admin"))
    kept = tmp_path / "Assayr Data-install-failed.log"
    assert "create-admin" in kept.read_text(encoding="utf-8")


def test_create_admin_only_when_no_administrator_exists(tmp_path):
    _, r = run_install(tmp_path)
    admin = next(cmd for cmd in r.calls if "create-admin" in cmd)
    assert "--if-no-admin" in admin


def test_install_clears_stale_services_first(tmp_path):
    _, r = run_install(tmp_path)
    assert idx_of(r, "sc.exe delete AssayrWeb") < idx_of(r, "initdb")


def test_finish_upgrade_failure_stops_and_removes_the_new_services(tmp_path):
    c, _ = run_install(tmp_path)

    def unhealthy(*a, **k):
        raise provision.HealthError("down")

    r = FakeRunner()
    with pytest.raises(ProvisionError):
        provision.finish_upgrade(c, r, wait=unhealthy)
    after_start = flat(r)[idx_of(r, "sc.exe start AssayrWeb") :]
    assert any("AssayrDb.exe uninstall" in cmd for cmd in after_start)


def test_busy_internal_ports_move_to_free_ones(tmp_path):
    import socket

    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    port = busy.getsockname()[1]
    try:
        c, _ = run_install(tmp_path, pg_port=port, api_port=port, clamav_port=port)
    finally:
        busy.close()
    assert port not in (c.pg_port, c.api_port, c.clamav_port)
    assert len({c.pg_port, c.api_port, c.clamav_port}) == 3
    assert InstallConfig.load(c.data_dir).pg_port == c.pg_port


def test_data_dir_acl_is_set_on_the_folder_and_children_inherit_it(tmp_path):
    c, r = run_install(tmp_path)
    icacls = [cmd for cmd in r.calls if cmd[0] == "icacls.exe" and "/inheritance:r" in cmd]
    assert icacls and "/T" not in icacls[0], "removing inheritance with /T leaves files with an empty ACL"
    reset = [cmd for cmd in r.calls if cmd[0] == "icacls.exe" and "/reset" in cmd]
    assert reset and reset[0][1] == str(c.data_dir / "*") and "/T" in reset[0]
    assert r.calls.index(icacls[0]) < r.calls.index(reset[0])


def test_data_folder_inside_the_program_folder_is_refused(tmp_path):
    c = make_cfg(tmp_path)
    c.data_dir = c.install_dir / "data"
    with pytest.raises(ProvisionError, match="separate"):
        provision.install(
            c, "a@b.c", "a-very-long-password", CertChoice("self-signed"), FakeRunner(), wait=healthy
        )


def test_program_folder_inside_the_data_folder_is_refused(tmp_path):
    c = make_cfg(tmp_path)
    c.data_dir = c.install_dir.parent
    with pytest.raises(ProvisionError, match="separate"):
        provision.install(
            c, "a@b.c", "a-very-long-password", CertChoice("self-signed"), FakeRunner(), wait=healthy
        )


def test_rollback_waits_until_the_restored_version_answers(tmp_path, monkeypatch):
    c, _ = run_install(tmp_path)
    monkeypatch.setattr(provision, "read_backup", lambda backup, work: work)
    monkeypatch.setattr(provision, "restore_data", lambda *a, **k: None)
    seen = []
    provision.rollback(
        c, tmp_path / "b.tar.gz", FakeRunner(), wait=lambda url, timeout, version: seen.append((url, version))
    )
    assert seen == [(c.health_url, c.version)]


def test_rollback_reports_a_version_that_never_answers(tmp_path, monkeypatch):
    c, _ = run_install(tmp_path)
    monkeypatch.setattr(provision, "read_backup", lambda backup, work: work)
    monkeypatch.setattr(provision, "restore_data", lambda *a, **k: None)

    def down(*a, **k):
        raise provision.HealthError("down")

    with pytest.raises(ProvisionError, match="down"):
        provision.rollback(c, tmp_path / "b.tar.gz", FakeRunner(), wait=down)
