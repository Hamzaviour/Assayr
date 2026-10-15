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


def test_start_order(tmp_path):
    c, r = cfg(tmp_path, malware_scan=False), FakeRunner()
    services.start_all(c, r)
    started = [call[2] for call in r.calls if call[:2] == ["sc.exe", "start"]]
    assert started == ["AssayrDb", "AssayrApi", "AssayrWorker", "AssayrWeb"]


def test_stop_order_is_dependents_first(tmp_path):
    scm = FakeScm(["AssayrDb", "AssayrClamAV", "AssayrApi", "AssayrWorker", "AssayrWeb"])
    services.stop_all(cfg(tmp_path), scm, sleep=lambda s: None)
    stopped = [call[2] for call in scm.calls if call[:2] == ["sc.exe", "stop"]]
    assert stopped == ["AssayrWeb", "AssayrWorker", "AssayrApi", "AssayrClamAV", "AssayrDb"]


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


DEPENDS = {
    "AssayrApi": ["AssayrDb"],
    "AssayrWorker": ["AssayrDb", "AssayrClamAV"],
    "AssayrWeb": ["AssayrApi"],
}


class FakeScm:
    """Behaves like the Windows service manager: a stop takes a query to complete, and a service
    whose dependents are still running refuses to stop (error 1051)."""

    def __init__(self, running):
        self.state = {name: "RUNNING" for name in running}
        self.calls = []

    def _dependents_running(self, name):
        return [
            s
            for s, deps in DEPENDS.items()
            if name in deps and self.state.get(s) in ("RUNNING", "STOP_PENDING")
        ]

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self.calls.append(args)
        out, code = "", 0
        if args[:2] == ["sc.exe", "stop"]:
            name = args[2]
            if name not in self.state:
                code = 1060
            elif self._dependents_running(name):
                code = 1051
            elif self.state[name] == "RUNNING":
                self.state[name] = "STOP_PENDING"
        elif args[:2] == ["sc.exe", "query"]:
            name = args[2]
            if name not in self.state:
                code = 1060
            else:
                if self.state[name] == "STOP_PENDING":
                    self.state[name] = "STOPPED"
                out = f"SERVICE_NAME: {name}\n        STATE              : 1  {self.state[name]}\n"
        elif len(args) == 2 and args[1] == "uninstall":
            name = args[0].rsplit("\\", 1)[-1].rsplit("/", 1)[-1].removesuffix(".exe")
            if self.state.get(name) not in (None, "STOPPED"):
                code = 1072
            self.state.pop(name, None)
        return subprocess.CompletedProcess(args, code, out, "")


ALL = ["AssayrDb", "AssayrClamAV", "AssayrApi", "AssayrWorker", "AssayrWeb"]


def test_stop_all_waits_so_every_service_really_stops(tmp_path):
    scm = FakeScm(ALL)
    services.stop_all(cfg(tmp_path), scm, sleep=lambda s: None)
    assert all(state == "STOPPED" for state in scm.state.values()), scm.state


def test_unregister_stops_everything_then_removes_it(tmp_path):
    c = cfg(tmp_path)
    for name in ALL:
        (c.services_dir / f"{name}.exe").write_bytes(b"MZ")
    scm = FakeScm(ALL)
    services.unregister(c, scm, sleep=lambda s: None)
    assert scm.state == {}


def test_stop_gives_up_with_a_clear_error(tmp_path):
    class Stuck(FakeScm):
        def run(self, args, **kw):
            result = super().run(args, **kw)
            self.state = {k: "RUNNING" if v != "STOPPED" else v for k, v in self.state.items()}
            return result

    try:
        services.stop(cfg(tmp_path), Stuck(["AssayrDb"]), "AssayrDb", timeout_s=3, sleep=lambda s: None)
    except services.CommandError as exc:
        assert "AssayrDb did not stop" in str(exc)
    else:
        raise AssertionError("expected CommandError")
