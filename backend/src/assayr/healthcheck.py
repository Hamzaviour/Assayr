"""Wait until Assayr answers its health endpoint."""

import json
import ssl
import time
import urllib.request
from urllib.parse import urlsplit


class HealthError(Exception):
    pass


def _fetch(url: str) -> dict:
    context = ssl.create_default_context()
    if urlsplit(url).hostname in ("localhost", "127.0.0.1"):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # the local install may use a self-signed certificate
    with urllib.request.urlopen(url, timeout=5, context=context) as response:  # noqa: S310
        return json.loads(response.read().decode())


def wait_healthy(
    url, timeout_s, expect_version=None, fetch=_fetch, sleep=time.sleep, clock=time.monotonic
) -> str:
    """Poll until the endpoint reports ok (and the expected version). Returns the version."""
    deadline = clock() + timeout_s
    problem = "no answer"
    while True:
        try:
            body = fetch(url)
            if body.get("status") == "ok" and (
                expect_version is None or body.get("version") == expect_version
            ):
                return body.get("version", "")
            problem = f"answered {body}"
        except (OSError, ValueError) as exc:
            problem = str(exc)
        if clock() >= deadline:
            raise HealthError(f"Assayr did not become healthy at {url} within {int(timeout_s)} s: {problem}")
        sleep(2)
