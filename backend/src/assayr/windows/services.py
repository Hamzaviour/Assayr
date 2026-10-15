"""Register and control the Assayr Windows services (WinSW wrappers, managed with sc.exe)."""

import re
import shutil
import time

from assayr.windows.layout import SERVICES, InstallConfig, active_services
from assayr.windows.render import render_service_xml
from assayr.windows.runner import CommandError, Runner

__all__ = [
    "CommandError",
    "account",
    "register",
    "start_all",
    "status",
    "stop",
    "stop_all",
    "unregister",
    "wait_running",
]

_STATE = re.compile(r"STATE\s*:\s*\d+\s+(\w+)")


def account(service: str) -> str:
    return f"NT SERVICE\\{service}"


def register(cfg: InstallConfig, runner: Runner) -> None:
    winsw = cfg.services_dir / "WinSW-x64.exe"
    for service in active_services(cfg):
        (cfg.services_dir / f"{service}.xml").write_text(render_service_xml(cfg, service), encoding="utf-8")
        exe = cfg.services_dir / f"{service}.exe"
        shutil.copyfile(winsw, exe)
        runner.run([exe, "install"])
        runner.run(["sc.exe", "config", service, "obj=", account(service)])


def stop(cfg: InstallConfig, runner: Runner, service: str, timeout_s: int = 90, sleep=time.sleep) -> None:
    """Ask a service to stop and wait until it has (a service that is not installed counts as stopped)."""
    for _ in range(int(timeout_s)):
        state = _state(runner, service)
        if state in (None, "STOPPED"):
            return
        if state == "RUNNING":
            runner.run(["sc.exe", "stop", service], check=False)
        sleep(1)
    raise CommandError(f"{service} did not stop within {timeout_s} s; see {cfg.logs_dir}")


def stop_all(cfg: InstallConfig, runner: Runner, sleep=time.sleep) -> None:
    """Stop every Assayr service, dependents first, waiting for each."""
    for service in reversed(SERVICES):
        stop(cfg, runner, service, sleep=sleep)


def _wait_gone(runner: Runner, service: str, sleep, timeout_s: int = 60) -> None:
    for _ in range(timeout_s):
        if _state(runner, service) is None:
            return
        sleep(1)


def unregister(cfg: InstallConfig, runner: Runner, sleep=time.sleep) -> None:
    """Stop and remove every Assayr service; best effort, so cleanup paths can always run it."""
    for service in reversed(SERVICES):
        try:
            stop(cfg, runner, service, sleep=sleep)
        except CommandError:
            pass  # removing it below still marks it for deletion
        exe = cfg.services_dir / f"{service}.exe"
        if exe.exists():
            runner.run([exe, "uninstall"], check=False)
        else:
            runner.run(["sc.exe", "delete", service], check=False)
        _wait_gone(runner, service, sleep)


def start_all(cfg: InstallConfig, runner: Runner) -> None:
    for service in active_services(cfg):
        runner.run(["sc.exe", "start", service], check=False)


def _state(runner: Runner, service: str) -> str | None:
    match = _STATE.search(runner.run(["sc.exe", "query", service], check=False).stdout or "")
    return match.group(1) if match else None


def status(cfg: InstallConfig, runner: Runner) -> dict[str, str]:
    return {service: _state(runner, service) or "NOT INSTALLED" for service in active_services(cfg)}


def wait_running(
    cfg: InstallConfig, runner: Runner, service: str, timeout_s: int = 60, sleep=time.sleep
) -> None:
    for _ in range(int(timeout_s)):
        if _state(runner, service) == "RUNNING":
            return
        sleep(1)
    raise CommandError(f"{service} did not start; see {cfg.logs_dir}")
