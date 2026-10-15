import subprocess

import pytest

from assayr.windows import provision
from assayr.windows.layout import InstallConfig
from assayr.windows.provision import CertChoice, ProvisionError


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(provision.services, "wait_running", lambda *a, **k: None)


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls, self.envs, self.fail_on = [], [], fail_on

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self.calls.append(args)
        self.envs.append(env or {})
        if self.fail_on and any(self.fail_on in a for a in args):
            if check:
                raise provision.CommandError(f"{args[0]} {self.fail_on} failed")
            return subprocess.CompletedProcess(args, 1, "", "boom")
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
    assert any("-m assayr migrate" in cmd for cmd in flat(r))
    assert "0.4.0" in c.env_file.read_text()
    assert InstallConfig.load(c.data_dir).version == "0.4.0"


def test_finish_upgrade_health_failure_raises(tmp_path):
    c, _ = run_install(tmp_path)

    def unhealthy(*a, **k):
        raise provision.HealthError("down")

    with pytest.raises(ProvisionError, match="down"):
        provision.finish_upgrade(c, FakeRunner(), wait=unhealthy)
