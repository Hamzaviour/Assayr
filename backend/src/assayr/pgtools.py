"""Run PostgreSQL client tools against the Assayr database without putting the password on a command line."""

import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


class PgError(Exception):
    pass


class PgTools:
    def __init__(self, bin_dir: Path | None, url: str, run=subprocess.run) -> None:
        parts = urlsplit(url.replace("postgresql+pg8000://", "postgresql://", 1))
        self.host = parts.hostname or "127.0.0.1"
        self.port = str(parts.port or 5432)
        self.user = unquote(parts.username or "assayr")
        self.password = unquote(parts.password or "")
        self.db = parts.path.lstrip("/") or "assayr"
        self.bin_dir = bin_dir
        self._run = run

    def _tool(self, name: str) -> str:
        if self.bin_dir is None:
            return name
        return str(self.bin_dir / (name + (".exe" if os.name == "nt" else "")))

    def _call(self, args: list[str]) -> None:
        env = {**os.environ, "PGPASSWORD": self.password}
        result = self._run(args, env=env, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            err = (result.stderr or b"").decode(errors="replace").strip()
            raise PgError(f"{Path(args[0]).name} failed: {err}")

    def _conn(self) -> list[str]:
        return ["-h", self.host, "-p", self.port, "-U", self.user]

    def dump(self, path: Path) -> None:
        self._call([self._tool("pg_dump"), *self._conn(), "-d", self.db, "-Fc", "-f", str(path)])

    def recreate_database(self) -> None:
        self._call([self._tool("dropdb"), *self._conn(), "--if-exists", "--force", self.db])
        self._call([self._tool("createdb"), *self._conn(), "-O", self.user, self.db])

    def restore(self, path: Path) -> None:
        self._call(
            [
                self._tool("pg_restore"),
                *self._conn(),
                "-d",
                self.db,
                "--no-owner",
                "--exit-on-error",
                str(path),
            ]
        )
