"""Where a Windows installation keeps its program and data, and the settings chosen at install time."""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

SERVICES: tuple[str, ...] = ("AssayrDb", "AssayrClamAV", "AssayrApi", "AssayrWorker", "AssayrWeb")


@dataclass
class InstallConfig:
    install_dir: Path
    data_dir: Path
    hostname: str
    org_name: str
    https_port: int = 443
    http_port: int = 80
    web_mode: str = "https"  # https | http
    behind_tls_proxy: bool = False
    malware_scan: bool = True
    pg_port: int = 5432
    api_port: int = 8000
    version: str = ""

    def __post_init__(self) -> None:
        self.install_dir = Path(self.install_dir)
        self.data_dir = Path(self.data_dir)

    python_exe = property(lambda self: self.install_dir / "python" / "python.exe")
    pg_bin = property(lambda self: self.install_dir / "pgsql" / "bin")
    caddy_exe = property(lambda self: self.install_dir / "caddy" / "caddy.exe")
    clamd_exe = property(lambda self: self.install_dir / "clamav" / "clamd.exe")
    bundled_signatures = property(lambda self: self.install_dir / "clamav" / "database")
    web_root = property(lambda self: self.install_dir / "web")
    services_dir = property(lambda self: self.install_dir / "services")
    db_dir = property(lambda self: self.data_dir / "db")
    blobs_dir = property(lambda self: self.data_dir / "blobs")
    certs_dir = property(lambda self: self.data_dir / "certs")
    clamav_db_dir = property(lambda self: self.data_dir / "clamav")
    backups_dir = property(lambda self: self.data_dir / "backups")
    logs_dir = property(lambda self: self.data_dir / "logs")
    license_dir = property(lambda self: self.data_dir / "license")
    env_file = property(lambda self: self.data_dir / "assayr.env")
    caddyfile = property(lambda self: self.data_dir / "Caddyfile")
    clamd_conf = property(lambda self: self.data_dir / "clamd.conf")
    install_json = property(lambda self: self.data_dir / "install.json")
    install_log = property(lambda self: self.data_dir / "install.log")

    @property
    def health_url(self) -> str:
        if self.web_mode == "http":
            return f"http://localhost:{self.http_port}/api/v1/healthz"
        return f"https://localhost:{self.https_port}/api/v1/healthz"

    def save(self) -> None:
        data = {k: str(v) if isinstance(v, Path) else v for k, v in asdict(self).items()}
        self.install_json.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, data_dir: Path) -> "InstallConfig":
        raw = json.loads((Path(data_dir) / "install.json").read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})


def active_services(cfg: InstallConfig) -> list[str]:
    return [s for s in SERVICES if cfg.malware_scan or s != "AssayrClamAV"]
