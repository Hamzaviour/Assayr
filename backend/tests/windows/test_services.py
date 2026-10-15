import subprocess

from assayr.windows import services
from assayr.windows.layout import InstallConfig


class FakeRunner:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self.calls.append(args)
        return subprocess.CompletedProcess(args, 0, self.replies.get(tuple(args[:3]), ""), "")


def cfg(tmp_path, **kw):
    c = InstallConfig(
        tmp_path / "Program Files" / "Assayr", tmp_path / "data", "h", "o", version="0.3.0", **kw
    )
    c.services_dir.mkdir(parents=True)
    (c.services_dir / "WinSW-x64.exe").write_bytes(b"MZ")
    return c


def test_register_writes_xml_and_sets_virtual_account(tmp_path):
    c, r = cfg(tmp_path), FakeRunner()
    services.register(c, r)
    assert (c.services_dir / "AssayrApi.xml").exists() and (c.services_dir / "AssayrApi.exe").exists()
    assert [str(c.services_dir / "AssayrApi.exe"), "install"] in r.calls
    assert ["sc.exe", "config", "AssayrApi", "obj=", "NT SERVICE\\AssayrApi"] in r.calls


def test_start_order_and_stop_reverse(tmp_path):
    c, r = cfg(tmp_path, malware_scan=False), FakeRunner()
    services.start_all(c, r)
    services.stop_all(c, r)
    started = [call[2] for call in r.calls if call[:2] == ["sc.exe", "start"]]
    stopped = [call[2] for call in r.calls if call[:2] == ["sc.exe", "stop"]]
    assert started == ["AssayrDb", "AssayrApi", "AssayrWorker", "AssayrWeb"]
    assert stopped == list(reversed(started))


def test_status_parses_sc_query(tmp_path):
    c = cfg(tmp_path)
    running = "SERVICE_NAME: AssayrDb\n        STATE              : 4  RUNNING\n"
    result = services.status(c, FakeRunner({("sc.exe", "query", "AssayrDb"): running}))
    assert result["AssayrDb"] == "RUNNING" and result["AssayrApi"] == "NOT INSTALLED"


def test_wait_running_gives_up_with_log_hint(tmp_path):
    c = cfg(tmp_path)
    try:
        services.wait_running(c, FakeRunner(), "AssayrDb", timeout_s=3, sleep=lambda s: None)
    except services.CommandError as exc:
        assert "AssayrDb did not start" in str(exc) and str(c.logs_dir) in str(exc)
    else:
        raise AssertionError("expected CommandError")
