"""Run installer commands and record them in the install log, never with secrets."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

SECRET_ENV = ("ASSAYR_ADMIN_PASSWORD", "ASSAYR_PFX_PASSWORD", "PGPASSWORD")


class CommandError(Exception):
    pass


class Runner(Protocol):
    def run(self, args, *, env=None, input=None, check=True) -> subprocess.CompletedProcess: ...


class SubprocessRunner:
    """Runs commands and appends `RUN <args>` and the exit code to the install log.

    Environment values and stdin are never logged, so passwords passed that way stay out of the log.
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path

    def _log(self, line: str) -> None:
        """Logging is best effort: a log that cannot be written must not stop the install or its cleanup."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ} {line}\n")
        except OSError:
            pass

    def run(self, args, *, env=None, input=None, check=True):
        args = [str(a) for a in args]
        self._log("RUN " + subprocess.list2cmdline(args))
        result = subprocess.run(args, env=env, input=input, capture_output=True, text=True, check=False)  # noqa: S603
        self._log(f"EXIT {result.returncode}")
        for stream in (result.stdout, result.stderr):
            if stream and stream.strip():
                self._log(stream.strip()[-4000:])
        if check and result.returncode != 0:
            raise CommandError(
                f"{Path(args[0]).name} {' '.join(args[1:3])} failed (exit {result.returncode})."
            )
        return result
