"""Text of the files a Windows installation needs. Pure functions, so they test on any OS."""

from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from assayr.windows.layout import InstallConfig

# Mirrors frontend/site.caddy, with the API on localhost and the web root on disk.
_SITE = """\
encode zstd gzip
header {{
	X-Content-Type-Options nosniff
	X-Frame-Options DENY
	Referrer-Policy no-referrer
	Permissions-Policy "camera=(), microphone=(), geolocation=()"
	Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
	-Server
}}
handle /healthz {{
	respond "ok" 200
}}
handle /api/* {{
	request_body {{
		max_size 110MB
	}}
	reverse_proxy 127.0.0.1:{api_port}
}}
handle {{
	root * "{web_root}"
	try_files {{path}} /index.html
	file_server
}}
"""


def _env_value(value: str) -> str:
    """Double-quoted dotenv value; python-dotenv unescapes \\\\ and \\" inside double quotes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def database_url(cfg: InstallConfig, db_password: str) -> str:
    return f"postgresql+pg8000://assayr:{quote(db_password, safe='')}@127.0.0.1:{cfg.pg_port}/assayr"


def render_env(cfg: InstallConfig, db_password: str) -> str:
    secure = cfg.web_mode == "https" or cfg.behind_tls_proxy
    values = {
        "ASSAYR_VERSION": cfg.version,
        "POSTGRES_PASSWORD": db_password,
        "ASSAYR_DATABASE_URL": database_url(cfg, db_password),
        "ASSAYR_HOSTNAME": cfg.hostname,
        "ASSAYR_ORG_NAME": cfg.org_name,
        "ASSAYR_WEB_MODE": cfg.web_mode,
        "ASSAYR_HTTPS_PORT": str(cfg.https_port),
        "ASSAYR_HTTP_PORT": str(cfg.http_port),
        "ASSAYR_SECURE_COOKIES": "true" if secure else "false",
        "ASSAYR_MALWARE_SCAN": "true" if cfg.malware_scan else "false",
        "ASSAYR_CLAMAV_HOST": "127.0.0.1" if cfg.malware_scan else "",
        "ASSAYR_CLAMAV_PORT": "3310",
        "ASSAYR_STORAGE_DIR": str(cfg.blobs_dir),
    }
    lines = ["# Assayr settings. Restart Assayr after changing this file."]
    lines += [f"{k}={_env_value(v)}" for k, v in values.items()]
    return "\n".join(lines) + "\n"


def _indent(text: str) -> str:
    return "".join(f"\t{line}\n" if line else "\n" for line in text.splitlines())


def render_caddyfile(cfg: InstallConfig) -> str:
    site = _indent(_SITE.format(api_port=cfg.api_port, web_root=cfg.web_root.as_posix()))
    sni = f"\tdefault_sni {cfg.hostname}\n" if cfg.web_mode == "https" else ""
    head = "{\n\tadmin off\n\tauto_https off\n" + sni + "}\n\n"
    if cfg.web_mode == "http":
        return head + f":{cfg.http_port} {{\n{site}}}\n"
    crt, key = (cfg.certs_dir / "tls.crt").as_posix(), (cfg.certs_dir / "tls.key").as_posix()
    redirect = (
        f":{cfg.http_port} {{\n"
        '\thandle /healthz {\n\t\trespond "ok" 200\n\t}\n'
        f"\thandle {{\n\t\tredir https://{{host}}:{cfg.https_port}{{uri}} permanent\n\t}}\n}}\n"
    )
    return head + f':{cfg.https_port} {{\n\ttls "{crt}" "{key}"\n{site}}}\n\n' + redirect


def render_clamd_conf(cfg: InstallConfig) -> str:
    return (
        "TCPSocket 3310\nTCPAddr 127.0.0.1\n"
        f'DatabaseDirectory "{cfg.clamav_db_dir}"\n'
        f'LogFile "{cfg.logs_dir / "clamd.log"}"\nLogFileMaxSize 10M\nLogRotate yes\n'
        "StreamMaxLength 110M\nMaxFileSize 110M\nMaxScanSize 400M\n"
    )


def _service(cfg: InstallConfig, service: str) -> tuple[str, str, str, list[str], str]:
    """(display name, executable, arguments, dependencies, description)."""
    py = str(cfg.python_exe)
    if service == "AssayrDb":
        args = f'-D "{cfg.db_dir}" -p {cfg.pg_port} -c listen_addresses=127.0.0.1'
        return "Assayr Database", str(cfg.pg_bin / "postgres.exe"), args, [], "PostgreSQL for Assayr"
    if service == "AssayrClamAV":
        args = f'--foreground --config-file="{cfg.clamd_conf}"'
        return "Assayr ClamAV", str(cfg.clamd_exe), args, [], "Malware scanning for uploaded evidence"
    if service == "AssayrApi":
        args = (
            f"-m uvicorn assayr.main:create_app --factory --host 127.0.0.1 --port {cfg.api_port} "
            "--proxy-headers --forwarded-allow-ips 127.0.0.1"
        )
        return "Assayr API", py, args, ["AssayrDb"], "Assayr web API"
    if service == "AssayrWorker":
        deps = ["AssayrDb"] + (["AssayrClamAV"] if cfg.malware_scan else [])
        return "Assayr Worker", py, "-m assayr worker", deps, "Assayr evidence verification"
    if service == "AssayrWeb":
        args = f'run --config "{cfg.caddyfile}" --adapter caddyfile'
        return "Assayr Web", str(cfg.caddy_exe), args, ["AssayrApi"], "Assayr HTTPS front end"
    raise ValueError(service)


def render_service_xml(cfg: InstallConfig, service: str) -> str:
    """WinSW service definition."""
    name, exe, args, deps, description = _service(cfg, service)
    depends = "".join(f"  <depend>{d}</depend>\n" for d in deps)
    delayed = (
        "" if service in ("AssayrDb", "AssayrClamAV") else "  <delayedAutoStart>true</delayedAutoStart>\n"
    )
    restart = '  <onfailure action="restart" delay="10 sec"/>\n' * 3
    return (
        "<service>\n"
        f"  <id>{service}</id>\n"
        f"  <name>{escape(name)}</name>\n"
        f"  <description>{escape(description)}</description>\n"
        f"  <executable>{escape(exe)}</executable>\n"
        f"  <arguments>{escape(args)}</arguments>\n"
        f"  <workingdirectory>{escape(str(cfg.data_dir))}</workingdirectory>\n"
        f'  <env name="ASSAYR_ENV_FILE" value={quoteattr(str(cfg.env_file))}/>\n'
        '  <env name="PYTHONUTF8" value="1"/>\n'
        f"{depends}"
        "  <startmode>Automatic</startmode>\n"
        f"{delayed}"
        "  <stoptimeout>60 sec</stoptimeout>\n"
        f"{restart}"
        "  <resetfailure>1 hour</resetfailure>\n"
        f"  <logpath>{escape(str(cfg.logs_dir))}</logpath>\n"
        '  <log mode="roll-by-size"><sizeThreshold>10240</sizeThreshold><keepFiles>5</keepFiles></log>\n'
        "</service>\n"
    )
